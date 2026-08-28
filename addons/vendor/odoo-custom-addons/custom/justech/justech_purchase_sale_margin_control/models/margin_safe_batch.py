# -*- coding: utf-8 -*-
"""19.0.8.16.0 — Controlled SAFE historical MTX consolidation (no REVIEW/CONFLICT)."""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseSaleMarginTransactionSafeBatch(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    def consolidate_sale_transactions(self, sale_order, dry_run=False):
        """Merge complementary MTX of the same SO into one canonical. Idempotent.

        Only SAFE_TO_CONSOLIDATE. Never REVIEW/CONFLICT. dry_run writes nothing.
        """
        so = sale_order[:1]
        if not so:
            return self.browse()
        txs = self.search(
            [("sale_order_ids", "in", so.id), ("is_merged", "=", False)],
            order="id asc",
        )
        if len(txs) <= 1:
            return txs[:1]
        classification, _reasons = self._classify_sale_fragmentation_detail(so, txs)
        if classification != "SAFE_TO_CONSOLIDATE":
            _logger.warning(
                "MTX consolidation skipped for SO %s: %s among %s",
                so.name,
                classification,
                txs.mapped("transaction_number"),
            )
            return self.browse()
        canonical = self._choose_canonical(txs)
        if dry_run:
            return canonical
        secondaries = txs - canonical
        for sec in secondaries:
            canonical._merge_transaction_into(sec)
        canonical.invalidate_recordset()
        canonical._sync_lines_from_documents()
        canonical._invalidate_linked_document_trace()
        return canonical

    @api.model
    def _classify_sale_fragmentation(self, sale_order, txs):
        klass, _reasons = self._classify_sale_fragmentation_detail(sale_order, txs)
        return klass

    @api.model
    def _classify_sale_fragmentation_detail(self, sale_order, txs):
        """Return (classification, reasons). Origin text is never the sole SAFE criterion."""
        reasons = []
        if not txs or len(txs) <= 1:
            return "SAFE_TO_CONSOLIDATE", reasons
        so = sale_order[:1]
        companies = set(txs.mapped("company_id").ids)
        if so.company_id:
            companies.add(so.company_id.id)
        if len(companies) > 1:
            return "CONFLICT", ["compañías distintas en MTX/SO"]
        customers = {t.customer_id.id for t in txs if t.customer_id}
        if so.partner_id and customers and any(cid != so.partner_id.id for cid in customers):
            return "CONFLICT", ["cliente MTX incompatible con la SO"]
        extra_sos = set()
        for t in txs:
            extra_sos |= set(t.sale_order_ids.ids) - {so.id}
        if extra_sos:
            return "REVIEW_REQUIRED", ["MTX compartida con otras SO: %s" % sorted(extra_sos)]
        if len(txs) > 3:
            return "REVIEW_REQUIRED", ["más de 3 MTX (%s)" % len(txs)]

        invoices = txs.mapped("customer_invoice_ids")
        for inv in invoices:
            inv_sos = inv.invoice_line_ids.mapped("sale_line_ids.order_id")
            if inv_sos and so not in inv_sos:
                return "CONFLICT", ["factura cliente %s pertenece a otra venta" % (inv.name or inv.id)]
            other = inv_sos - so
            if other:
                return "REVIEW_REQUIRED", [
                    "factura %s también apunta a %s" % (inv.name or inv.id, other.mapped("name"))
                ]

        pos = txs.mapped("purchase_order_ids")
        Link = self.env["purchase.sale.cost.link"]
        for po in pos:
            po_sos = po.order_line.mapped("sale_line_id.order_id")
            if po_sos and so not in po_sos:
                return "CONFLICT", ["OC %s pertenece a otra venta" % po.name]
            other = po_sos - so
            if other:
                return "REVIEW_REQUIRED", ["OC %s también apunta a %s" % (po.name, other.mapped("name"))]
            has_link = Link.search_count(
                [("purchase_id", "=", po.id), ("sale_id", "=", so.id), ("state", "!=", "cancelled")]
            )
            if not po_sos and not has_link:
                other_mtx = self.search(
                    [
                        ("is_merged", "=", False),
                        ("purchase_order_ids", "in", po.id),
                        ("sale_order_ids", "!=", False),
                        ("id", "not in", txs.ids),
                    ],
                    limit=1,
                )
                if other_mtx:
                    return "REVIEW_REQUIRED", [
                        "OC %s también está en MTX %s de otra venta"
                        % (po.name, other_mtx.transaction_number)
                    ]
                if po.origin:
                    foreign = self.env["sale.order"].search(
                        [
                            ("name", "=", po.origin),
                            ("company_id", "=", po.company_id.id),
                            ("id", "!=", so.id),
                        ],
                        limit=1,
                    )
                    if foreign:
                        return "REVIEW_REQUIRED", [
                            "OC %s origin apunta a otra SO %s" % (po.name, foreign.name)
                        ]

        bills = txs.mapped("vendor_bill_ids")
        for bill in bills:
            bill_pos = bill.invoice_line_ids.mapped("purchase_line_id.order_id")
            if bill_pos and pos and not (bill_pos & pos):
                bill_sos = bill_pos.mapped("order_line.sale_line_id.order_id")
                if bill_sos and so not in bill_sos:
                    return "CONFLICT", ["bill %s de OC de otra venta" % (bill.name or bill.id)]
                if bill_sos - so:
                    return "REVIEW_REQUIRED", [
                        "bill %s relacionado con otras SO" % (bill.name or bill.id)
                    ]

        approved = txs.filtered(
            lambda t: t.state in ("approved", "closed") and t.approval_state == "approved"
        )
        if len(approved) > 1:
            po_sets = [set(t.purchase_order_ids.ids) for t in approved]
            if po_sets and po_sets[0] and any(po_sets[0] != s and s for s in po_sets[1:]):
                overlap = set(po_sets[0])
                for s in po_sets[1:]:
                    overlap &= s
                if not overlap:
                    return "REVIEW_REQUIRED", ["aprobaciones con OC disjuntas"]

        manuals = txs.filtered(lambda t: t.source == "manual")
        if manuals and invoices and len(set(invoices.mapped("partner_id").ids)) > 1:
            return "REVIEW_REQUIRED", ["relación manual con facturas de clientes distintos"]
        return "SAFE_TO_CONSOLIDATE", reasons

    @api.model
    def _union_docs(self, txs):
        return {
            "so": txs.mapped("sale_order_ids"),
            "po": txs.mapped("purchase_order_ids"),
            "inv": txs.mapped("customer_invoice_ids"),
            "bill": txs.mapped("vendor_bill_ids"),
        }

    @api.model
    def _signed_untaxed(self, moves, inbound=False):
        total = 0.0
        for move in moves.filtered(lambda m: m.state != "cancel"):
            amt = (
                move.amount_untaxed_signed
                if "amount_untaxed_signed" in move._fields
                else move.amount_untaxed
            )
            amt = abs(amt or 0.0)
            refund_types = ("in_refund",) if inbound else ("out_refund",)
            total += -amt if move.move_type in refund_types else amt
        return total

    @api.model
    def _financial_snapshot(self, sale_order, txs):
        """Deduplicated commercial figures for the SO (never sum overlapping MTX)."""
        so = sale_order[:1]
        docs = self._union_docs(txs)
        sale = so.amount_untaxed or 0.0
        if docs["inv"]:
            sale = self._signed_untaxed(docs["inv"], inbound=False) or sale
        if docs["bill"]:
            cost = self._signed_untaxed(docs["bill"], inbound=True)
        else:
            cost = sum(docs["po"].mapped("amount_untaxed") or [0.0])
        margin = sale - cost
        pct = (margin / sale * 100.0) if sale else 0.0
        return {
            "sale": sale,
            "cost": cost,
            "margin": margin,
            "pct": pct,
            "po_ids": docs["po"].ids,
            "bill_ids": docs["bill"].ids,
            "inv_ids": docs["inv"].ids,
            "po_names": docs["po"].mapped("name"),
            "bill_names": [n for n in docs["bill"].mapped("name") if n],
            "inv_names": [n for n in docs["inv"].mapped("name") if n],
        }

    @api.model
    def _amounts_close(self, a, b, digits=2):
        return abs((a or 0.0) - (b or 0.0)) <= (0.5 * 10 ** (-digits) + 1e-9)

    @api.model
    def preview_safe_consolidation(self, sale_order):
        """Dry-run dict. Never writes."""
        so = sale_order[:1]
        txs = self.search(
            [("sale_order_ids", "in", so.id), ("is_merged", "=", False)],
            order="id asc",
        )
        snap = self._financial_snapshot(so, txs)
        snap["mtx_sale_max"] = max(txs.mapped("display_sale_amount") or [0.0])
        snap["mtx_cost_max"] = max(txs.mapped("display_cost_amount") or [0.0])
        snap["mtx_margin_max"] = max(txs.mapped("display_margin_amount") or [0.0])
        if not so:
            return {"result": "BLOCKED", "reasons": ["SO vacía"], **snap}
        if len(txs) <= 1:
            return {
                "result": "ALREADY_CONSOLIDATED",
                "so": so.name,
                "so_id": so.id,
                "classification": "ALREADY_CONSOLIDATED",
                "canonical_id": txs[:1].id if txs else False,
                "canonical_number": txs[:1].transaction_number if txs else False,
                "secondary_ids": [],
                "secondary_numbers": [],
                "mtx_ids": txs.ids,
                "mtx_numbers": txs.mapped("transaction_number"),
                "reasons": [],
                "sale_after": snap["sale"],
                "cost_after": snap["cost"],
                "margin_after": snap["margin"],
                "pct_after": snap["pct"],
                **snap,
            }
        klass, reasons = self._classify_sale_fragmentation_detail(so, txs)
        canonical = self._choose_canonical(txs) if klass == "SAFE_TO_CONSOLIDATE" else self.browse()
        secondaries = (txs - canonical) if canonical else txs
        result = {
            "SAFE_TO_CONSOLIDATE": "SAFE_OK",
            "REVIEW_REQUIRED": "REVIEW",
            "CONFLICT": "CONFLICT",
        }.get(klass, "BLOCKED")
        return {
            "result": result,
            "so": so.name,
            "so_id": so.id,
            "classification": klass,
            "canonical_id": canonical.id if canonical else False,
            "canonical_number": canonical.transaction_number if canonical else False,
            "secondary_ids": secondaries.ids,
            "secondary_numbers": secondaries.mapped("transaction_number"),
            "mtx_ids": txs.ids,
            "mtx_numbers": txs.mapped("transaction_number"),
            "reasons": reasons,
            "sale_after": snap["sale"],
            "cost_after": snap["cost"],
            "margin_after": snap["margin"],
            "pct_after": snap["pct"],
            **snap,
        }

    def consolidate_if_safe(self, sale_order):
        """Write path: only SAFE_OK. Raises if post-check financials drift."""
        preview = self.preview_safe_consolidation(sale_order)
        if preview["result"] != "SAFE_OK":
            return preview
        so = sale_order[:1]
        canonical = self.consolidate_sale_transactions(so, dry_run=False)
        if not canonical:
            preview["result"] = "BLOCKED"
            preview["reasons"] = preview.get("reasons") or ["consolidación no aplicó"]
            return preview
        canonical.invalidate_recordset()
        after_sale = canonical.display_sale_amount
        after_cost = canonical.display_cost_amount
        after_margin = canonical.display_margin_amount
        sale_ok = self._amounts_close(after_sale, preview["sale"]) or self._amounts_close(
            after_sale, preview.get("mtx_sale_max")
        )
        cost_ok = self._amounts_close(after_cost, preview["cost"]) or self._amounts_close(
            after_cost, preview.get("mtx_cost_max")
        )
        margin_ok = self._amounts_close(after_margin, preview["margin"]) or self._amounts_close(
            after_margin, preview.get("mtx_margin_max")
        )
        if not (sale_ok and cost_ok and margin_ok):
            raise UserError(
                _(
                    "Financial drift after consolidating %(so)s: "
                    "sale %(s0)s→%(s1)s cost %(c0)s→%(c1)s margin %(m0)s→%(m1)s"
                )
                % {
                    "so": so.name,
                    "s0": preview["sale"],
                    "s1": after_sale,
                    "c0": preview["cost"],
                    "c1": after_cost,
                    "m0": preview["margin"],
                    "m1": after_margin,
                }
            )
        active = self.search_count(
            [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
        )
        if active != 1:
            raise UserError(
                _("Expected 1 active MTX for %s after merge, found %s") % (so.name, active)
            )
        preview["result"] = "CONSOLIDATED"
        preview["canonical_id"] = canonical.id
        preview["sale_after"] = after_sale
        preview["cost_after"] = after_cost
        preview["margin_after"] = after_margin
        preview["pct_after"] = canonical.display_margin_pct
        return preview

    def action_consolidate_duplicates_for_sales(self):
        sos = self.mapped("sale_order_ids")
        for so in sos:
            self.consolidate_sale_transactions(so, dry_run=False)
        return True
