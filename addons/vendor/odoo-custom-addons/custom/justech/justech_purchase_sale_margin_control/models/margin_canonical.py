# -*- coding: utf-8 -*-
"""Canonical MTX: one commercial sale → one active purchase.sale.margin.transaction.

Does not delete historical records. Merged MTX stay for audit with merged_into_id.
"""
import logging

from odoo import _, api, fields, models

from .margin_cross_trace import join_record_names

_logger = logging.getLogger(__name__)

STATE_RANK = {
    "closed": 70,
    "approved": 60,
    "validated": 50,
    "pending_review": 40,
    "reopened": 35,
    "detected": 30,
    "draft": 20,
    "rejected": 5,
}


class PurchaseSaleMarginTransactionCanonical(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    is_merged = fields.Boolean(
        string="Consolidada",
        default=False,
        index=True,
        copy=False,
        help="True si esta operación fue fusionada en otra MTX canónica. No es operación activa.",
    )
    merged_into_id = fields.Many2one(
        "purchase.sale.margin.transaction",
        string="Fusionada en",
        index=True,
        copy=False,
        ondelete="restrict",
    )
    merged_at = fields.Datetime(string="Fusionada el", copy=False, readonly=True)
    merged_by_id = fields.Many2one("res.users", string="Fusionada por", copy=False, readonly=True)
    consolidation_note = fields.Text(string="Nota de consolidación", copy=False)

    def _operational_domain(self):
        return [("is_merged", "=", False)]

    @api.model
    def _extract_m2m_ids(self, commands):
        ids = []
        for cmd in commands or []:
            if not isinstance(cmd, (list, tuple)) or not cmd:
                continue
            if cmd[0] == 6:
                ids.extend(cmd[2] or [])
            elif cmd[0] in (4, 1) and len(cmd) > 1:
                ids.append(cmd[1])
        return [i for i in ids if i]

    def _attach_document_vals(self, vals):
        """Merge incoming create/write document commands onto an existing MTX."""
        self.ensure_one()
        writes = {}
        mapping = (
            ("sale_order_ids", self.sale_order_ids),
            ("purchase_order_ids", self.purchase_order_ids),
            ("customer_invoice_ids", self.customer_invoice_ids),
            ("vendor_bill_ids", self.vendor_bill_ids),
            ("supplier_ids", self.supplier_ids),
        )
        for fname, recs in mapping:
            new_ids = self._extract_m2m_ids(vals.get(fname))
            add = [i for i in new_ids if i not in recs.ids]
            if add:
                writes[fname] = [(4, i) for i in add]
        for scalar in ("customer_id", "company_id", "salesperson_id"):
            if vals.get(scalar) and not self[scalar]:
                writes[scalar] = vals[scalar]
        if writes:
            self.write(writes)
        return self

    @api.model
    def find_canonical_for_sale(self, sale_order, company=None):
        """Locate the active canonical MTX for a sale.order.

        Priority: 1 SO exact, 2 customer invoice of that SO, 3 PO originated from SO,
        4 explicit cost links. Origin text is never the sole criterion.
        """
        if not sale_order:
            return self.browse()
        so = sale_order[:1]
        company = company or so.company_id
        base = [("is_merged", "=", False), ("company_id", "=", company.id)]

        txs = self.search(base + [("sale_order_ids", "in", so.id)], order="id asc")
        if txs:
            return self._choose_canonical(txs)

        invoices = so.invoice_ids.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund") and m.state != "cancel"
        )
        if invoices:
            txs = self.search(base + [("customer_invoice_ids", "in", invoices.ids)], order="id asc")
            if txs:
                return self._choose_canonical(txs)

        Purchase = self.env["purchase.order"]
        pos = Purchase.search(
            [
                ("company_id", "=", company.id),
                ("order_line.sale_line_id.order_id", "=", so.id),
            ]
        )
        if pos:
            txs = self.search(base + [("purchase_order_ids", "in", pos.ids)], order="id asc")
            if txs:
                return self._choose_canonical(txs)

        Link = self.env["purchase.sale.cost.link"]
        links = Link.search(
            [("sale_id", "=", so.id), ("state", "!=", "cancelled"), ("purchase_id", "!=", False)]
        )
        if links:
            txs = self.search(
                base + [("purchase_order_ids", "in", links.mapped("purchase_id").ids)],
                order="id asc",
            )
            if txs:
                return self._choose_canonical(txs)
        return self.browse()

    @api.model
    def _choose_canonical(self, txs):
        """Prefer the MTX that already holds costs+sale; then more docs; then workflow rank; then oldest."""
        active = txs.filtered(lambda t: not t.is_merged) or txs
        if not active:
            return self.browse()
        if len(active) == 1:
            return active

        def score(tx):
            has_sale = bool(tx.sale_order_ids or tx.customer_invoice_ids)
            has_cost = bool(tx.purchase_order_ids or tx.vendor_bill_ids)
            docs = (
                len(tx.sale_order_ids)
                + len(tx.purchase_order_ids)
                + len(tx.customer_invoice_ids)
                + len(tx.vendor_bill_ids)
            )
            return (
                1 if (has_sale and has_cost) else 0,
                1 if has_cost else 0,
                STATE_RANK.get(tx.state, 0),
                docs,
                -tx.id,
            )

        return max(list(active), key=score)

    @api.model
    def find_or_create_canonical_transaction(self, sale_order=None, customer_invoice=None, vals=None):
        """Idempotent: reuse active MTX for the SO / customer invoice, else create one."""
        vals = dict(vals or {})
        so = sale_order
        inv = customer_invoice
        if not so and inv:
            so = inv.invoice_line_ids.mapped("sale_line_ids.order_id")[:1]
        company = vals.get("company_id") and self.env["res.company"].browse(vals["company_id"])
        if so:
            company = company or so.company_id
            existing = self.find_canonical_for_sale(so, company=company)
            if existing:
                if inv and inv.id not in existing.customer_invoice_ids.ids:
                    vals.setdefault("customer_invoice_ids", [(4, inv.id)])
                if so.id not in existing.sale_order_ids.ids:
                    vals.setdefault("sale_order_ids", [(4, so.id)])
                existing._attach_document_vals(vals)
                _logger.info(
                    "Canonical MTX reuse %s for SO %s",
                    existing.transaction_number,
                    so.name,
                )
                return existing
        elif inv:
            company = company or inv.company_id
            existing = self.search(
                [
                    ("is_merged", "=", False),
                    ("company_id", "=", company.id),
                    ("customer_invoice_ids", "in", inv.id),
                ],
                limit=1,
                order="id asc",
            )
            if existing:
                existing._attach_document_vals(vals)
                return existing

        create_vals = {
            "company_id": (company or self.env.company).id,
            "transaction_type": vals.get("transaction_type") or "resale",
            "source": vals.get("source") or "auto_detected",
            "state": vals.get("state") or "draft",
        }
        create_vals.update({k: v for k, v in vals.items() if k not in create_vals})
        if so:
            create_vals.setdefault("name", so.name)
            create_vals.setdefault("customer_id", so.partner_id.id)
            create_vals.setdefault("sale_order_ids", [(6, 0, [so.id])])
            if so.user_id:
                create_vals.setdefault("salesperson_id", so.user_id.id)
        if inv:
            create_vals.setdefault("name", inv.name or inv.ref or create_vals.get("name"))
            create_vals.setdefault("customer_id", inv.partner_id.id)
            create_vals.setdefault("customer_invoice_ids", [(6, 0, [inv.id])])
        return self.with_context(skip_canonical_reuse=True).create(create_vals)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("allow_parallel_margin_tx") or self.env.context.get(
            "skip_canonical_reuse"
        ):
            return super().create(vals_list)
        to_create = []
        reused = self.browse()
        for vals in vals_list:
            so_ids = self._extract_m2m_ids(vals.get("sale_order_ids"))
            if len(so_ids) == 1:
                so = self.env["sale.order"].browse(so_ids[0])
                existing = self.find_canonical_for_sale(so, company=so.company_id)
                if existing:
                    _logger.warning(
                        "Prevented parallel MTX for SO %s; reusing %s",
                        so.name,
                        existing.transaction_number,
                    )
                    existing._attach_document_vals(vals)
                    reused |= existing
                    continue
            to_create.append(vals)
        created = super().create(to_create) if to_create else self.browse()
        return reused | created

    def write(self, vals):
        res = super().write(vals)
        if vals.get("sale_order_ids") and not self.env.context.get("skip_canonical_reuse"):
            for rec in self.filtered(lambda t: not t.is_merged):
                for so in rec.sale_order_ids:
                    canon = rec.find_canonical_for_sale(so)
                    if canon and canon.id != rec.id:
                        _logger.warning(
                            "MTX %s linked to SO %s whose canonical is %s — not auto-merging on write",
                            rec.transaction_number,
                            so.name,
                            canon.transaction_number,
                        )
        return res

    def consolidate_sale_transactions(self, sale_order):
        """Merge complementary MTX of the same SO into one canonical. Idempotent.

        Does not delete the secondary. Marks it is_merged with merged_into_id.
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
        classification = self._classify_sale_fragmentation(so, txs)
        if classification == "CONFLICT":
            _logger.warning(
                "MTX consolidation skipped for SO %s: CONFLICT among %s",
                so.name,
                txs.mapped("transaction_number"),
            )
            return self.browse()
        canonical = self._choose_canonical(txs)
        secondaries = txs - canonical
        for sec in secondaries:
            canonical._merge_transaction_into(sec)
        canonical.invalidate_recordset()
        canonical._sync_lines_from_documents()
        canonical._invalidate_linked_document_trace()
        return canonical

    @api.model
    def _classify_sale_fragmentation(self, sale_order, txs):
        """SAFE_TO_CONSOLIDATE | REVIEW_REQUIRED | CONFLICT"""
        if not txs or len(txs) == 1:
            return "SAFE_TO_CONSOLIDATE"
        customers = {t.customer_id.id for t in txs if t.customer_id}
        if len(customers) > 1:
            return "CONFLICT"
        companies = set(txs.mapped("company_id").ids)
        if len(companies) > 1:
            return "CONFLICT"
        so_sets = [set(t.sale_order_ids.ids) for t in txs]
        extra_sos = set()
        for s in so_sets:
            extra_sos |= s - {sale_order.id}
        if extra_sos:
            return "REVIEW_REQUIRED"
        if len(txs) > 3:
            return "REVIEW_REQUIRED"
        approved = txs.filtered(lambda t: t.state in ("approved", "closed") and t.approval_state == "approved")
        if len(approved) > 1:
            po_sets = [set(t.purchase_order_ids.ids) for t in approved]
            if po_sets and po_sets[0] and any(po_sets[0] != s and s for s in po_sets[1:]):
                overlap = po_sets[0]
                for s in po_sets[1:]:
                    overlap &= s
                if not overlap:
                    return "REVIEW_REQUIRED"
        return "SAFE_TO_CONSOLIDATE"

    def _merge_transaction_into(self, secondary):
        """Move missing links from secondary onto self; keep secondary as audit stub."""
        self.ensure_one()
        secondary.ensure_one()
        if secondary.id == self.id or secondary.is_merged:
            return
        note = _(
            "Consolidated into %(canon)s on %(when)s. "
            "Documents moved: SO=%(so)s PO=%(po)s INV=%(inv)s BILL=%(bill)s. "
            "Secondary state %(state)s / validation %(val)s / approval %(apr)s preserved."
        ) % {
            "canon": self.transaction_number,
            "when": fields.Datetime.now(),
            "so": join_record_names(secondary.sale_order_ids),
            "po": join_record_names(secondary.purchase_order_ids),
            "inv": join_record_names(secondary.customer_invoice_ids),
            "bill": join_record_names(secondary.vendor_bill_ids),
            "state": secondary.state,
            "val": secondary.validation_state,
            "apr": secondary.approval_state,
        }
        # Mark merged first so uniqueness constraints ignore this stub while
        # documents are attached onto the canonical MTX.
        secondary.write(
            {
                "is_merged": True,
                "merged_into_id": self.id,
                "merged_at": fields.Datetime.now(),
                "merged_by_id": self.env.uid,
                "consolidation_note": note,
            }
        )
        writes = {}
        for fname in (
            "sale_order_ids",
            "purchase_order_ids",
            "customer_invoice_ids",
            "vendor_bill_ids",
            "supplier_ids",
        ):
            add = secondary[fname] - self[fname]
            if add:
                writes[fname] = [(4, r.id) for r in add]
        if writes:
            self.with_context(skip_line_sync=True, skip_canonical_reuse=True).write(writes)

        Alloc = self.env["purchase.sale.cost.allocation"]
        allocs = Alloc.search([("transaction_id", "=", secondary.id)])
        if allocs:
            allocs.write({"transaction_id": self.id})

        Aux = self.env["purchase.sale.payable.auxiliary"]
        auxs = Aux.search([("transaction_ids", "in", secondary.id)])
        for aux in auxs:
            aux.write({"transaction_ids": [(3, secondary.id), (4, self.id)]})

        # Lines are rebuilt from documents on canonical; do not duplicate.
        # Keep secondary lines for audit.
        secondary.message_post(body=note)
        self.message_post(
            body=_("Merged MTX %s (%s) into this canonical operation.")
            % (secondary.transaction_number, secondary.name or "")
        )
        _logger.info(
            "Merged MTX %s into canonical %s for audit trail",
            secondary.transaction_number,
            self.transaction_number,
        )

    def action_consolidate_duplicates_for_sales(self):
        """Admin action: consolidate each linked SO."""
        sos = self.mapped("sale_order_ids")
        for so in sos:
            self.consolidate_sale_transactions(so)
        return True
