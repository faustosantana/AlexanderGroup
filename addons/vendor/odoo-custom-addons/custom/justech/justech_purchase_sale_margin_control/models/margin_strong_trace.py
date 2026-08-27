# -*- coding: utf-8 -*-
"""19.0.8.29.9 — Confirmed Sale↔PO relation: sale_line_id OR origin exact.

LEVEL 1: POL.sale_line_id → SOL (line-strong)
LEVEL 2: explicit persisted relation (wizard / Trace assignment if present)
LEVEL 3: PO.origin = SO.name exact + same company + single candidate

Never invents sale_line_id.
Never auto-confirms ORIGIN_MULTIPLE / cross-company / heuristics.
Never touches account.move amounts, stock, payments, or NCF.
"""
import logging
import re

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_CONFIRMED_MTX_STATES = frozenset({"validated", "approved", "closed"})
_AUTO_CONFIRM_FROM = frozenset({"draft", "detected", "pending_review", "reopened"})
_COMMITTED_PO_STATES = frozenset({"purchase", "done"})
_ORIGIN_MULTI_CHARS = re.compile(r"[,/;|]")


class PurchaseSaleMarginTransactionStrongTrace(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    # ------------------------------------------------------------------
    # Origin resolution (company-scoped, never invents line FKs)
    # ------------------------------------------------------------------
    @api.model
    def _classify_po_origin(self, po):
        """Return (class, sale.order recordset) for a purchase.order.

        Classes: ORIGIN_EXACT_SINGLE | ORIGIN_MULTIPLE | ORIGIN_INVALID |
                 ORIGIN_CROSS_COMPANY | ORIGIN_AMBIGUOUS | ORIGIN_EMPTY
        """
        SaleOrder = self.env["sale.order"]
        origin = (po.origin or "").strip()
        if not origin:
            return "ORIGIN_EMPTY", SaleOrder.browse()
        if _ORIGIN_MULTI_CHARS.search(origin) or "http://" in origin or "https://" in origin:
            # Contaminated / multi-doc origin — never auto-link whole PO.
            exact = SaleOrder.search(
                [("name", "=", origin), ("company_id", "=", po.company_id.id)], limit=2
            )
            if len(exact) == 1:
                # pathological: origin equals name but also has URL — still treat exact if equal
                if origin == exact.name:
                    return "ORIGIN_EXACT_SINGLE", exact
            return "ORIGIN_MULTIPLE", SaleOrder.browse()
        exact = SaleOrder.search(
            [("name", "=", origin), ("company_id", "=", po.company_id.id)]
        )
        if len(exact) == 1:
            return "ORIGIN_EXACT_SINGLE", exact
        if len(exact) > 1:
            return "ORIGIN_AMBIGUOUS", exact
        other = SaleOrder.search([("name", "=", origin), ("company_id", "!=", po.company_id.id)])
        if other:
            return "ORIGIN_CROSS_COMPANY", other
        return "ORIGIN_INVALID", SaleOrder.browse()

    @api.model
    def _resolve_origin_sale_order(self, po):
        """Return SO only for ORIGIN_EXACT_SINGLE; else empty."""
        klass, sos = self._classify_po_origin(po)
        if klass == "ORIGIN_EXACT_SINGLE":
            return sos
        return self.env["sale.order"].browse()

    def _strong_sale_po_links(self, include_cancelled=False):
        """(so, po) with Level-1 sale_line_id.

        Cancelled POs excluded by default (active cost); pass include_cancelled
        for historical relation confirmation.
        """
        self.ensure_one()
        links = []
        sos = self.sale_order_ids
        pos = self.purchase_order_ids
        if not include_cancelled:
            pos = pos.filtered(lambda p: p.state != "cancel")
        if not (sos and pos):
            return links
        so_ids = set(sos.ids)
        for po in pos:
            for pol in po.order_line.filtered(
                lambda l: l.sale_line_id and l.sale_line_id.order_id.id in so_ids
            ):
                links.append((pol.sale_line_id.order_id, po))
                break
        return links

    def _has_strong_sale_po_trace(self):
        self.ensure_one()
        return bool(self._strong_sale_po_links())

    def _has_confirmed_sale_po_relation(self):
        """LEVEL 1 / 2 / 3 — enough to auto-confirm relation (no Vendor Bill).

        Cancelled POs still count for *relation* (historical), not for committed cost.
        """
        self.ensure_one()
        return bool(
            self._strong_sale_po_links(include_cancelled=True)
            or self._has_explicit_relation_trace()
            or self._origin_exact_links(include_cancelled=True)
        )

    def _origin_exact_links(self, include_cancelled=False):
        """(so, po) with Level-3 origin exact. Cancelled optional (historical relation)."""
        self.ensure_one()
        links = []
        sos = self.sale_order_ids
        pos = self.purchase_order_ids
        if not include_cancelled:
            pos = pos.filtered(lambda p: p.state != "cancel")
        if not (sos and pos):
            return links
        so_by_id = {s.id: s for s in sos}
        for po in pos:
            klass, resolved = self._classify_po_origin(po)
            if klass != "ORIGIN_EXACT_SINGLE":
                continue
            so = resolved[:1]
            if so.id in so_by_id:
                links.append((so, po))
        return links

    def _has_origin_exact_trace(self):
        self.ensure_one()
        return bool(self._origin_exact_links())

    def _explicit_relation_links(self):
        """Level-2: Trace qty assignment rows if any exist for hub SO+PO."""
        self.ensure_one()
        links = []
        Assignment = self.env.get("justech.purchase.sale.qty.assignment")
        if Assignment is None:
            return links
        sos = self.sale_order_ids
        pos = self.purchase_order_ids.filtered(lambda p: p.state != "cancel")
        if not (sos and pos):
            return links
        rows = Assignment.search(
            [
                ("sale_order_id", "in", sos.ids),
                ("purchase_order_id", "in", pos.ids),
                ("state", "not in", ("cancelled", "cancel")),
            ]
        )
        for row in rows:
            if row.sale_order_id and row.purchase_order_id:
                links.append((row.sale_order_id, row.purchase_order_id))
        return links

    def _has_explicit_relation_trace(self):
        self.ensure_one()
        return bool(self._explicit_relation_links())

    def _line_coverage_status(self):
        """COMPLETE / PARTIAL / NONE / UNAVAILABLE for sale lines vs sale_line_id."""
        self.ensure_one()
        sos = self.sale_order_ids
        if not sos:
            return "UNAVAILABLE", 0, 0
        sale_lines = sos.mapped("order_line").filtered(
            lambda l: not l.display_type
        )
        if not sale_lines:
            return "UNAVAILABLE", 0, 0
        linked = sale_lines.filtered(
            lambda l: bool(
                self.env["purchase.order.line"].search_count(
                    [("sale_line_id", "=", l.id)], limit=1
                )
            )
        )
        total, n_linked = len(sale_lines), len(linked)
        if n_linked == 0:
            return "NONE", total, 0
        if n_linked >= total:
            return "COMPLETE", total, n_linked
        return "PARTIAL", total, n_linked

    def _strong_trace_sale_po_bill_pairs(self):
        self.ensure_one()
        pairs = []
        sos = self.sale_order_ids
        pos = self.purchase_order_ids.filtered(lambda p: p.state != "cancel")
        bills = self.vendor_bill_ids.filtered(
            lambda m: m.state == "posted" and m.move_type in ("in_invoice", "in_refund")
        )
        if not (sos and pos and bills):
            return pairs
        so_ids = set(sos.ids)
        bill_ids = set(bills.ids)
        MoveLine = self.env["account.move.line"]
        for po in pos:
            strong_pols = po.order_line.filtered(
                lambda l: l.sale_line_id and l.sale_line_id.order_id.id in so_ids
            )
            # Also allow bill via any POL of related PO (origin relation, no sale_line_id)
            pols = strong_pols or po.order_line
            if not pols:
                continue
            amls = MoveLine.search(
                [
                    ("purchase_line_id", "in", pols.ids),
                    ("move_id", "in", list(bill_ids)),
                ]
            )
            for aml in amls:
                bill = aml.move_id
                if bill.state != "posted":
                    continue
                so = (
                    aml.purchase_line_id.sale_line_id.order_id
                    if aml.purchase_line_id.sale_line_id
                    else (sos[:1] if sos else False)
                )
                if so:
                    pairs.append((so, po, bill))
        return pairs

    def _has_strong_sale_po_bill_trace(self):
        self.ensure_one()
        return bool(self._strong_trace_sale_po_bill_pairs())

    def _cost_document_stage(self):
        self.ensure_one()
        pos = self.purchase_order_ids.filtered(lambda p: p.state != "cancel")
        bills = self.vendor_bill_ids.filtered(
            lambda m: m.state == "posted" and m.move_type in ("in_invoice", "in_refund")
        )
        committed_pos = pos.filtered(lambda p: p.state in _COMMITTED_PO_STATES)
        draft_pos = pos.filtered(lambda p: p.state in ("draft", "sent", "to approve"))
        if bills and committed_pos:
            invoiced_po_ids = set(
                bills.mapped("invoice_line_ids.purchase_line_id.order_id").ids
            )
            if invoiced_po_ids and set(committed_pos.ids) - invoiced_po_ids:
                return "partial", _("PARCIALMENTE FACTURADA")
            return "invoiced", _("FACTURADO")
        if bills and not committed_pos:
            return "invoiced", _("FACTURADO")
        if committed_pos:
            return "committed", _("OC RELACIONADA · SIN FACTURA")
        if draft_pos:
            return "provisional", _("OC ABIERTA (RFQ)")
        return "none", _("SIN FACTURA")

    def _classify_trace_strength(self):
        self.ensure_one()
        if self._has_strong_sale_po_bill_trace() and self._has_strong_sale_po_trace():
            return "STRONG_CONFIRMED"
        if self._has_strong_sale_po_trace():
            return "STRONG_SALE_PO"
        if self._has_explicit_relation_trace():
            return "EXPLICIT_RELATION"
        if self._has_origin_exact_trace():
            return "ORIGIN_EXACT"
        sos = self.sale_order_ids
        pos = self.purchase_order_ids.filtered(lambda p: p.state != "cancel")
        bills = self.vendor_bill_ids.filtered(
            lambda m: m.state == "posted" and m.move_type in ("in_invoice", "in_refund")
        )
        bill_po_fk = False
        if pos and bills:
            for bill in bills:
                if bill.invoice_line_ids.mapped("purchase_line_id.order_id") & pos:
                    bill_po_fk = True
                    break
        if bill_po_fk and not sos:
            return "STRONG_PO_BILL"
        for po in self.purchase_order_ids:
            klass, _sos = self._classify_po_origin(po)
            if klass == "ORIGIN_MULTIPLE":
                return "ORIGIN_MULTIPLE"
            if klass == "ORIGIN_CROSS_COMPANY":
                return "ORIGIN_CROSS_COMPANY"
        if sos and pos and any((po.origin or "").strip() == so.name for so in sos for po in pos):
            return "HEURISTIC"
        if not sos and pos:
            return "UNRELATED"
        if sos and not pos:
            return "UNRELATED"
        return "UNRELATED" if not (sos or pos or bills) else "AMBIGUOUS"

    def action_auto_confirm_strong_trace(self):
        """Validate MTX when LEVEL 1/2/3 Sale↔PO evidence exists (no bill required)."""
        confirmed = self.env["purchase.sale.margin.transaction"]
        for rec in self:
            if rec.state in _CONFIRMED_MTX_STATES:
                continue
            if rec.state not in _AUTO_CONFIRM_FROM:
                continue
            if not rec._has_confirmed_sale_po_relation():
                continue
            vals = {
                "state": "validated",
                "validation_state": "validated",
                "validated_by_id": self.env.user.id,
                "validated_at": fields.Datetime.now(),
            }
            if rec.link_mode in (False, "historical", "suggested"):
                vals["link_mode"] = "automatic"
            rec.with_context(justech_strong_trace_autoconfirm=True).write(vals)
            confirmed |= rec
            _logger.info(
                "Margins SO↔PO auto-confirm MTX %s (%s) → validated (origin_ok=%s strong=%s)",
                rec.id,
                rec.display_name,
                rec._has_origin_exact_trace(),
                rec._has_strong_sale_po_trace(),
            )
        return confirmed

    @api.model
    def _cron_auto_confirm_strong_trace(self):
        candidates = self.search(
            [
                ("state", "in", list(_AUTO_CONFIRM_FROM)),
                ("sale_order_ids", "!=", False),
                ("purchase_order_ids", "!=", False),
            ]
        )
        return candidates.action_auto_confirm_strong_trace()

    @api.model
    def action_backfill_origin_sale_po_relations(
        self, dry_run=False, sale_order_ids=None, purchase_order_ids=None
    ):
        """Idempotent historical backfill for LEVEL 1 + LEVEL 3 relations.

        Creates/updates MTX only. Never writes SO/PO/AML/stock/payment/NCF.
        Never invents sale_line_id.
        Never steals vendor bills already linked to another MTX.
        """
        PurchaseOrder = self.env["purchase.order"]
        SaleOrder = self.env["sale.order"]
        stats = {
            "SAFE_UPDATE_EXISTING_MTX": 0,
            "SAFE_CREATE_MTX": 0,
            "SAFE_ADD_PO_TO_MTX": 0,
            "Relations_validated": 0,
            "NO_ACTION": 0,
            "NEEDS_REVIEW": 0,
            "AMBIGUOUS": 0,
            "CROSS_COMPANY": 0,
            "Duplicates": 0,
            "bills_skipped_conflict": 0,
            "pairs": [],
        }
        domain = [("company_id", "!=", False)]
        if purchase_order_ids:
            domain.append(("id", "in", list(purchase_order_ids)))
        pos = PurchaseOrder.search(domain)
        seen_pairs = set()
        for po in pos:
            sos = SaleOrder.browse()
            for pol in po.order_line.filtered(lambda l: l.sale_line_id):
                sos |= pol.sale_line_id.order_id.filtered(
                    lambda s: s.company_id == po.company_id
                )
            klass, origin_sos = self._classify_po_origin(po)
            if klass == "ORIGIN_EXACT_SINGLE":
                sos |= origin_sos
            elif klass == "ORIGIN_MULTIPLE":
                stats["NEEDS_REVIEW"] += 1
                continue
            elif klass == "ORIGIN_CROSS_COMPANY":
                stats["CROSS_COMPANY"] += 1
                continue
            elif klass == "ORIGIN_AMBIGUOUS":
                stats["AMBIGUOUS"] += 1
                continue
            if sale_order_ids:
                sos = sos.filtered(lambda s: s.id in sale_order_ids)
            for so in sos:
                key = (so.id, po.id)
                if key in seen_pairs:
                    stats["Duplicates"] += 1
                    continue
                seen_pairs.add(key)
                existing = self.search(
                    [
                        ("company_id", "=", so.company_id.id),
                        ("sale_order_ids", "in", so.ids),
                    ],
                    limit=1,
                )
                action = "NO_ACTION"
                if not existing:
                    action = "SAFE_CREATE_MTX"
                elif po.id not in existing.purchase_order_ids.ids:
                    action = "SAFE_ADD_PO_TO_MTX"
                elif existing.state not in _CONFIRMED_MTX_STATES:
                    action = "SAFE_UPDATE_EXISTING_MTX"
                else:
                    stats["NO_ACTION"] += 1
                    stats["pairs"].append(
                        {
                            "so": so.name,
                            "po": po.name,
                            "action": action,
                            "mtx": existing.display_name,
                        }
                    )
                    continue

                stats["pairs"].append(
                    {
                        "so": so.name,
                        "po": po.name,
                        "action": action,
                        "mtx": existing.display_name if existing else False,
                    }
                )
                if dry_run:
                    stats[action] = stats.get(action, 0) + 1
                    continue

                if action == "SAFE_CREATE_MTX":
                    tx = self.find_or_create_canonical_transaction(
                        sale_order=so,
                        vals={
                            "company_id": so.company_id.id,
                            "name": so.name,
                            "customer_id": so.partner_id.id,
                            "sale_order_ids": [(4, so.id)],
                            "purchase_order_ids": [(4, po.id)],
                            "supplier_ids": [(4, po.partner_id.id)] if po.partner_id else False,
                            "transaction_type": "resale",
                            "source": "backfill",
                            "link_mode": "automatic",
                            "state": "detected",
                        },
                    )
                    stats["SAFE_CREATE_MTX"] += 1
                else:
                    tx = existing
                    writes = {}
                    if po.id not in tx.purchase_order_ids.ids:
                        writes["purchase_order_ids"] = [(4, po.id)]
                        if po.partner_id:
                            writes["supplier_ids"] = [(4, po.partner_id.id)]
                        stats["SAFE_ADD_PO_TO_MTX"] += 1
                    else:
                        stats["SAFE_UPDATE_EXISTING_MTX"] += 1
                    if writes:
                        tx.with_context(skip_line_sync=True).write(writes)
                # Attach posted vendor bills only if free (no other MTX owns them)
                bills = getattr(po, "invoice_ids", self.env["account.move"]).filtered(
                    lambda m: m.move_type in ("in_invoice", "in_refund") and m.state == "posted"
                )
                free_bills = self.env["account.move"]
                for bill in bills:
                    owners = self.search([("vendor_bill_ids", "in", bill.ids)])
                    if (owners - tx) and bill.id not in tx.vendor_bill_ids.ids:
                        stats["bills_skipped_conflict"] += 1
                        continue
                    if bill.id not in tx.vendor_bill_ids.ids:
                        free_bills |= bill
                if free_bills:
                    tx.with_context(skip_line_sync=True).write(
                        {"vendor_bill_ids": [(4, b.id) for b in free_bills]}
                    )
                try:
                    tx._sync_lines_from_documents()
                except Exception as exc:  # noqa: BLE001 — backfill must continue
                    _logger.warning("Backfill sync lines MTX %s: %s", tx.id, exc)
                before = tx.state
                confirmed = tx.action_auto_confirm_strong_trace()
                if confirmed or tx.state in _CONFIRMED_MTX_STATES:
                    if before not in _CONFIRMED_MTX_STATES:
                        stats["Relations_validated"] += 1
        return stats


class PurchaseOrderStrongTraceAutoConfirm(models.Model):
    _inherit = "purchase.order"

    def _justech_auto_link_margin_from_sale(self):
        """After SO→PO auto-link (sale_line_id and/or origin exact), auto-confirm."""
        res = super()._justech_auto_link_margin_from_sale()
        Transaction = self.env["purchase.sale.margin.transaction"]
        txs = Transaction.browse()
        for po in self.filtered(lambda p: p.state != "cancel"):
            # Ensure origin-exact SO is linked even if _get_sale_orders missed it
            so = Transaction._resolve_origin_sale_order(po)
            if so and po.state in ("purchase", "done", "draft", "sent"):
                tx = Transaction.find_or_create_canonical_transaction(
                    sale_order=so,
                    vals={
                        "company_id": po.company_id.id,
                        "name": so.name,
                        "customer_id": so.partner_id.id,
                        "sale_order_ids": [(4, so.id)],
                        "purchase_order_ids": [(4, po.id)],
                        "supplier_ids": [(4, po.partner_id.id)] if po.partner_id else False,
                        "transaction_type": "resale",
                        "source": "auto_detected",
                        "link_mode": "automatic",
                        "state": "detected",
                    },
                )
                if po.id not in tx.purchase_order_ids.ids:
                    tx.with_context(skip_line_sync=True).write(
                        {"purchase_order_ids": [(4, po.id)]}
                    )
                txs |= tx
            if po.order_line.filtered(lambda l: l.sale_line_id):
                found = Transaction.search(
                    [
                        ("company_id", "=", po.company_id.id),
                        ("purchase_order_ids", "in", po.ids),
                    ]
                )
                txs |= found
            # Origin-linked MTX search
            if so:
                found = Transaction.search(
                    [
                        ("company_id", "=", po.company_id.id),
                        "|",
                        ("purchase_order_ids", "in", po.ids),
                        ("sale_order_ids", "in", so.ids),
                    ]
                )
                txs |= found
        if txs:
            txs.sudo().action_auto_confirm_strong_trace()
        return res

    def create(self, vals_list):
        records = super().create(vals_list)
        # Future automation: origin set at create → ensure MTX (no financial writes)
        to_link = records.filtered(lambda p: (p.origin or "").strip())
        if to_link:
            to_link._justech_auto_link_margin_from_sale()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "origin" in vals:
            self.filtered(lambda p: (p.origin or "").strip())._justech_auto_link_margin_from_sale()
        return res


class AccountMoveStrongTraceAutoConfirm(models.Model):
    _inherit = "account.move"

    def _justech_auto_link_margin_documents(self):
        """After bill auto-link, keep relation confirmed (SO↔PO already enough)."""
        res = super()._justech_auto_link_margin_documents()
        Transaction = self.env["purchase.sale.margin.transaction"]
        txs = Transaction.browse()
        for move in self.filtered(
            lambda m: m.state == "posted" and m.move_type in ("in_invoice", "in_refund")
        ):
            pos = move.invoice_line_ids.mapped("purchase_line_id.order_id")
            if not pos:
                continue
            found = Transaction.search(
                [
                    ("company_id", "=", move.company_id.id),
                    "|",
                    ("purchase_order_ids", "in", pos.ids),
                    ("vendor_bill_ids", "in", move.ids),
                ]
            )
            txs |= found
        if txs:
            txs.sudo().action_auto_confirm_strong_trace()
        return res
