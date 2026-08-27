# -*- coding: utf-8 -*-
import datetime
import logging

from odoo import api, fields, models

from odoo.addons.justech_purchase_sale_margin_control.models import margin_acl

_logger = logging.getLogger(__name__)

# Audit approved confidence scale per trace source. "origin" can never reach
# 100 (rule: "origin alone never 100"); only an explicit purchase-line -> sale
# -line bridge (or a shared procurement group) can auto-confirm.
CONFIDENCE_BY_SOURCE = {
    "purchase_line": 100,
    "bill_purchase_sale": 95,
    "procurement": 95,
    "origin_single": 90,
    "origin_ambiguous": 65,
    "origin_product_qty": 80,
    "product_qty_company": 70,
    "ref": 55,
    "analytic": 45,
    "heuristic": 40,
    "manual": 0,
}

AUTO_CONFIRM_THRESHOLD = 90
SUGGEST_THRESHOLD = 70


class PurchaseSaleTraceEngine(models.AbstractModel):
    """Finds the sale order / sale order line behind a purchase order line or
    vendor bill line, following the audit approved priority chain:

    purchase_line_id (bill -> PO line -> SO line) -> procurement group ->
    PO origin -> product+qty+company -> document reference -> analytic
    account -> broad heuristic -> manual.
    """

    _name = "purchase.sale.trace.engine"
    _description = "Motor de trazabilidad compra-venta"

    # ------------------------------------------------------------------
    # Individual trace steps. Each returns a list of
    # (sale_order, sale_order_line_or_False, source, confidence) tuples.
    # ------------------------------------------------------------------
    @api.model
    def _resolve_purchase_line(self, purchase_line, bill_line):
        return purchase_line or (bill_line.purchase_line_id if bill_line else False)

    @api.model
    def _step_purchase_line(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        if not po_line:
            return []
        sale_line = getattr(po_line, "sale_line_id", False)
        if sale_line:
            return [(sale_line.order_id, sale_line, "purchase_line", CONFIDENCE_BY_SOURCE["purchase_line"])]
        return []

    @api.model
    def _step_procurement(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        if not po_line:
            return []
        Move = self.env["stock.move"]
        if "purchase_line_id" not in Move._fields:
            return []
        moves = Move.search([("purchase_line_id", "=", po_line.id)])
        if not moves:
            return []

        # Odoo 19 may not expose procurement group_id on stock.move.
        # Prefer group when present; otherwise bridge via sale_line_id on sibling moves
        # that share the same picking/origin.
        candidates = []
        seen = set()

        if "group_id" in Move._fields:
            group_ids = moves.mapped("group_id").ids
            if group_ids:
                sale_moves = Move.search(
                    [("group_id", "in", group_ids), ("sale_line_id", "!=", False)]
                )
                for move in sale_moves:
                    sale_line = move.sale_line_id
                    if not sale_line or sale_line.id in seen:
                        continue
                    seen.add(sale_line.id)
                    candidates.append(
                        (
                            sale_line.order_id,
                            sale_line,
                            "procurement",
                            CONFIDENCE_BY_SOURCE["procurement"],
                        )
                    )
                return candidates

        # Fallback without group_id: match sale moves sharing picking origin / move origin.
        origins = set(filter(None, moves.mapped("origin") + moves.mapped("picking_id.origin")))
        if not origins or "sale_line_id" not in Move._fields:
            return []
        sale_moves = Move.search(
            [
                ("sale_line_id", "!=", False),
                ("company_id", "=", po_line.company_id.id),
                "|",
                ("origin", "in", list(origins)),
                ("picking_id.origin", "in", list(origins)),
            ]
        )
        for move in sale_moves:
            sale_line = move.sale_line_id
            if not sale_line or sale_line.id in seen:
                continue
            if sale_line.product_id and po_line.product_id and sale_line.product_id != po_line.product_id:
                continue
            seen.add(sale_line.id)
            candidates.append(
                (
                    sale_line.order_id,
                    sale_line,
                    "procurement",
                    CONFIDENCE_BY_SOURCE["procurement"],
                )
            )
        return candidates

    @api.model
    def _step_origin(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        po = po_line.order_id if po_line else False
        if not po or not po.origin:
            return []
        origin = po.origin.strip()
        if not origin:
            return []
        Sale = self.env["sale.order"]
        sales = Sale.search([("name", "=", origin), ("company_id", "=", po.company_id.id)])
        if not sales:
            for token in origin.replace(";", ",").split(","):
                token = token.strip()
                if token:
                    sales |= Sale.search([("name", "=", token), ("company_id", "=", po.company_id.id)])
        if len(sales) == 1:
            return [
                (sales[0], False, "origin", CONFIDENCE_BY_SOURCE["origin_single"])
            ]
        # Multiple SO names in origin: never auto-confirm on origin alone
        return [
            (sale, False, "origin", CONFIDENCE_BY_SOURCE["origin_ambiguous"])
            for sale in sales
        ]

    @api.model
    def _step_product_qty_company(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        if not po_line or not po_line.product_id:
            return []
        company = po_line.company_id
        date_order = po_line.order_id.date_order or fields.Datetime.now()
        window_start = date_order - datetime.timedelta(days=60)
        window_end = date_order + datetime.timedelta(days=60)
        SaleLine = self.env["sale.order.line"]
        domain = [
            ("product_id", "=", po_line.product_id.id),
            ("company_id", "=", company.id),
            ("order_id.state", "in", ("sale", "done")),
            ("order_id.date_order", ">=", window_start),
            ("order_id.date_order", "<=", window_end),
        ]
        candidates = []
        qty = po_line.product_qty
        for sale_line in SaleLine.search(domain):
            if qty and sale_line.product_uom_qty and abs(sale_line.product_uom_qty - qty) > max(qty * 0.2, 1):
                continue
            candidates.append(
                (sale_line.order_id, sale_line, "product_qty_company", CONFIDENCE_BY_SOURCE["product_qty_company"])
            )
        return candidates

    @api.model
    def _step_ref(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        po = po_line.order_id if po_line else False
        if not po:
            return []
        ref_values = {v for v in (po.partner_ref, po.origin) if v}
        if bill_line and bill_line.move_id and bill_line.move_id.ref:
            ref_values.add(bill_line.move_id.ref)
        if not ref_values:
            return []
        Sale = self.env["sale.order"]
        candidates = []
        for ref in ref_values:
            sales = Sale.search(
                [
                    ("company_id", "=", po.company_id.id),
                    "|",
                    ("client_order_ref", "=", ref),
                    ("name", "=", ref),
                ]
            )
            for sale in sales:
                candidates.append((sale, False, "ref", CONFIDENCE_BY_SOURCE["ref"]))
        return candidates

    @api.model
    def _step_analytic(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        if not po_line:
            return []
        distribution = getattr(po_line, "analytic_distribution", None) or {}
        account_ids = set()
        for key in distribution.keys():
            for part in str(key).split(","):
                part = part.strip()
                if part.isdigit():
                    account_ids.add(int(part))
        if not account_ids:
            return []
        Sale = self.env["sale.order"]
        candidates = []
        sale_field = "analytic_account_id" if "analytic_account_id" in Sale._fields else False
        if not sale_field:
            return []
        sales = Sale.search(
            [(sale_field, "in", list(account_ids)), ("company_id", "=", po_line.company_id.id)]
        )
        for sale in sales:
            candidates.append((sale, False, "analytic", CONFIDENCE_BY_SOURCE["analytic"]))
        return candidates

    @api.model
    def _step_heuristic(self, purchase_line, bill_line):
        po_line = self._resolve_purchase_line(purchase_line, bill_line)
        if not po_line or not po_line.product_id:
            return []
        SaleLine = self.env["sale.order.line"]
        sales_lines = SaleLine.search(
            [
                ("product_id", "=", po_line.product_id.id),
                ("company_id", "=", po_line.company_id.id),
                ("order_id.state", "in", ("sale", "done")),
            ],
            limit=10,
        )
        return [
            (sl.order_id, sl, "heuristic", CONFIDENCE_BY_SOURCE["heuristic"]) for sl in sales_lines
        ]

    _STEP_METHODS = (
        "purchase_line",
        "procurement",
        "origin",
        "product_qty_company",
        "ref",
        "analytic",
        "heuristic",
    )

    @api.model
    def find_trace_candidates(self, purchase_line=None, bill_line=None):
        """Run the configured/default trace priority chain and return the
        candidates found at the first step that produced a match."""
        company = None
        if purchase_line:
            company = purchase_line.company_id
        elif bill_line:
            company = bill_line.company_id
        company = company or self.env.company

        order = self.env["purchase.sale.reconciliation.rule"].get_trace_priority(company)
        step_fns = {
            "purchase_line": self._step_purchase_line,
            "procurement": self._step_procurement,
            "origin": self._step_origin,
            "product_qty_company": self._step_product_qty_company,
            "ref": self._step_ref,
            "analytic": self._step_analytic,
            "heuristic": self._step_heuristic,
        }
        for code in order:
            fn = step_fns.get(code)
            if not fn:
                continue
            candidates = fn(purchase_line, bill_line)
            if candidates:
                return candidates
        return []

    @api.model
    def find_best_match(self, purchase_line=None, bill_line=None):
        """Return a finalized dict {sale_order, sale_line, source, confidence,
        ambiguous} or None. Confidence is capped and flagged ambiguous when
        more than one distinct sale order is found for the same step."""
        candidates = self.find_trace_candidates(purchase_line=purchase_line, bill_line=bill_line)
        if not candidates:
            return None
        distinct_orders = {c[0].id for c in candidates if c[0]}
        best = max(candidates, key=lambda c: c[3])
        sale_order, sale_line, source, confidence = best
        ambiguous = len(distinct_orders) > 1
        if ambiguous:
            confidence = min(confidence, SUGGEST_THRESHOLD - 1)
        return {
            "sale_order": sale_order,
            "sale_line": sale_line,
            "source": source,
            "confidence": confidence,
            "ambiguous": ambiguous,
            "candidates": candidates,
        }

    @api.model
    def confidence_to_state(self, confidence, ambiguous=False):
        if confidence >= AUTO_CONFIRM_THRESHOLD and not ambiguous:
            return "confirmed"
        if confidence >= SUGGEST_THRESHOLD:
            return "suggested"
        return "draft"

    # ------------------------------------------------------------------
    # Cost link helpers
    # ------------------------------------------------------------------
    @api.model
    def _company_amount(self, amount, currency, company):
        if not currency or not company or currency == company.currency_id:
            return amount
        return currency._convert(amount, company.currency_id, company, fields.Date.context_today(self))

    @api.model
    def build_link_vals(self, purchase_line, match=None):
        """Pure computation (no writes) of the vals that would be used to
        create/update a purchase.sale.cost.link for this PO line."""
        if match is None:
            match = self.find_best_match(purchase_line=purchase_line)
        company = purchase_line.company_id
        vals = {
            "company_id": company.id,
            "purchase_id": purchase_line.order_id.id,
            "purchase_line_id": purchase_line.id,
            "product_id": purchase_line.product_id.id,
            "currency_id": purchase_line.currency_id.id,
            "committed_amount": purchase_line.price_subtotal,
            "committed_amount_company": self._company_amount(
                purchase_line.price_subtotal, purchase_line.currency_id, company
            ),
        }
        if match:
            vals.update(
                {
                    "sale_id": match["sale_order"].id if match["sale_order"] else False,
                    "sale_line_id": match["sale_line"].id if match["sale_line"] else False,
                    "link_source": match["source"],
                    "confidence": match["confidence"],
                    "state": self.confidence_to_state(match["confidence"], match["ambiguous"]),
                }
            )
        return vals

    @api.model
    def preview_link_for_purchase_line(self, purchase_line):
        """Read-only preview used by dry-run backfills. Never writes to the
        database."""
        Link = self.env["purchase.sale.cost.link"]
        existing = Link.search([("purchase_line_id", "=", purchase_line.id)], limit=1)
        match = self.find_best_match(purchase_line=purchase_line)
        return {
            "exists": bool(existing),
            "link": existing,
            "would_update": bool(existing and not (existing.is_manual and existing.state == "confirmed") and match),
            "vals": self.build_link_vals(purchase_line, match=match),
            "match": match,
        }

    @api.model
    def get_or_create_link_for_purchase_line(self, purchase_line):
        # Technical Margin write — sudo on cost.link only (invoice/PO stay as user).
        Link = margin_acl.margin_cost_link(self.env)
        existing = Link.search([("purchase_line_id", "=", purchase_line.id)], limit=1)
        if existing:
            self.recompute_link(existing)
            return existing
        vals = self.build_link_vals(purchase_line)
        return Link.create(vals)

    @api.model
    def recompute_link(self, link):
        """Refresh trace fields on an existing link. Never touches links that
        are manually confirmed (rule: never overwrite confirmed manual
        allocations/links)."""
        link.ensure_one()
        if link.is_manual and link.state == "confirmed":
            return False
        match = self.find_best_match(purchase_line=link.purchase_line_id)
        if not match:
            return False
        link.write(
            {
                "sale_id": match["sale_order"].id if match["sale_order"] else link.sale_id.id,
                "sale_line_id": match["sale_line"].id if match["sale_line"] else False,
                "link_source": match["source"],
                "confidence": match["confidence"],
                "state": self.confidence_to_state(match["confidence"], match["ambiguous"]),
            }
        )
        return True

    # ------------------------------------------------------------------
    # Cost allocation helpers (vendor bill line -> sale order)
    # ------------------------------------------------------------------
    @api.model
    def _allocation_vals_from_link(self, link, bill_line):
        amount = bill_line.price_subtotal
        state = self.confidence_to_state(link.confidence, ambiguous=False)
        return {
            "link_id": link.id,
            "company_id": bill_line.company_id.id,
            "vendor_bill_id": bill_line.move_id.id,
            "vendor_bill_line_id": bill_line.id,
            "purchase_order_id": link.purchase_id.id,
            "purchase_order_line_id": link.purchase_line_id.id,
            "sale_order_id": link.sale_id.id if link.sale_id else False,
            "sale_order_line_id": link.sale_line_id.id if link.sale_line_id else False,
            "partner_id": link.sale_id.partner_id.id if link.sale_id else False,
            "supplier_id": bill_line.move_id.partner_id.id,
            "product_id": bill_line.product_id.id,
            "currency_id": bill_line.currency_id.id,
            "source_amount": amount,
            "allocated_amount": amount,
            "allocation_method": "line",
            "cost_usage_type": link.cost_usage_type,
            "source": link.link_source or "manual",
            "confidence": link.confidence,
            "state": state,
        }

    @api.model
    def preview_allocation_for_bill_line(self, bill_line):
        Allocation = self.env["purchase.sale.cost.allocation"]
        existing = Allocation.search([("vendor_bill_line_id", "=", bill_line.id)], limit=1)
        if existing and existing.is_manual and existing.state == "confirmed":
            return {"exists": True, "locked": True, "allocation": existing, "vals": {}}
        if not bill_line.purchase_line_id:
            return {"exists": bool(existing), "locked": False, "allocation": existing, "vals": {}}
        link_preview = self.preview_link_for_purchase_line(bill_line.purchase_line_id)
        link = link_preview["link"] if link_preview["exists"] else None
        sale_id = False
        if link:
            sale_id = link.sale_id.id
        elif link_preview["match"]:
            sale_id = link_preview["match"]["sale_order"].id
        if not sale_id:
            return {"exists": bool(existing), "locked": False, "allocation": existing, "vals": {}}
        return {
            "exists": bool(existing),
            "locked": False,
            "allocation": existing,
            "vals": {"sale_order_id": sale_id, "amount": bill_line.price_subtotal},
        }

    @api.model
    def create_suggested_allocation(self, bill_line):
        """Ensure a purchase.sale.cost.link and a matching cost allocation
        exist for a posted vendor bill line. Never overwrites a confirmed
        manual allocation."""
        if not bill_line.purchase_line_id:
            return False
        link = self.get_or_create_link_for_purchase_line(bill_line.purchase_line_id)
        if not link or not link.sale_id:
            return False
        Allocation = margin_acl.margin_cost_allocation(self.env)
        existing = Allocation.search([("vendor_bill_line_id", "=", bill_line.id)], limit=1)
        if existing:
            if existing.is_manual and existing.state == "confirmed":
                return existing
            existing.write(self._allocation_vals_from_link(link, bill_line))
            return existing
        vals = self._allocation_vals_from_link(link, bill_line)
        return Allocation.create(vals)

    # ------------------------------------------------------------------
    # Cron entry points (kept safe/idempotent; both crons ship inactive)
    # ------------------------------------------------------------------
    @api.model
    def cron_recompute_pending_links(self, batch_size=500):
        links = self.env["purchase.sale.cost.link"].search(
            [("state", "in", ("draft", "suggested"))], limit=batch_size
        )
        updated = 0
        for link in links:
            try:
                if self.recompute_link(link):
                    updated += 1
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "purchase_sale_margin_control: fallo al recalcular el enlace %s", link.id
                )
        _logger.info(
            "purchase_sale_margin_control: recompute cron revisó %s enlaces, actualizó %s",
            len(links),
            updated,
        )
        return True
