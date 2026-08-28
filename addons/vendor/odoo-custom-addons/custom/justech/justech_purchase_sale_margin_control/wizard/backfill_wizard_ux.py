# -*- coding: utf-8 -*-
"""Enhancements 19.0.4.0.0 — backfill histórico completo para dashboard/bandejas.

Extiende el wizard existente: además de links/allocations y SO→operación,
incluye facturas cliente, facturas proveedor (auxiliar CxP), compras sin venta
y enlaces seguros vía sale_line_id. Nunca aprueba operaciones ni toca contabilidad.
"""
from odoo import _, fields, models

from .backfill_wizard import BACKFILL_YEAR  # noqa: F401


class PurchaseSaleBackfillWizardUX(models.TransientModel):
    _inherit = "purchase.sale.backfill.wizard"

    batch_size = fields.Integer(
        default=0,
        string="Tamaño de lote",
        help="0 = sin límite (recomendado para backfill completo de 2026 en DEV).",
    )
    scanned_customer_invoices = fields.Integer(readonly=True)
    scanned_vendor_bills = fields.Integer(readonly=True)
    auxiliaries_created = fields.Integer(readonly=True)
    secure_relations = fields.Integer(readonly=True, string="Relaciones seguras")
    suggested_relations = fields.Integer(readonly=True, string="Relaciones sugeridas")
    ambiguous_relations = fields.Integer(readonly=True, string="Relaciones ambiguas")

    def _search_limit(self):
        return self.batch_size or None

    def _run_link_allocation_backfill(self, Trace, companies, counters):
        """Override to honour batch_size=0 as unlimited."""
        po_lines = self.env["purchase.order.line"].search(
            [
                ("company_id", "in", companies.ids),
                ("order_id.date_order", ">=", self.date_from),
                ("order_id.date_order", "<=", self.date_to),
                ("order_id.state", "in", ("purchase", "done")),
                ("display_type", "=", False),
            ],
            limit=self._search_limit(),
        )
        Link = self.env["purchase.sale.cost.link"]
        for line in po_lines:
            counters["scanned_po_lines"] += 1
            existed = Link.search_count([("purchase_line_id", "=", line.id)])
            if self.dry_run:
                preview = Trace.preview_link_for_purchase_line(line)
                if not preview["exists"] and preview["match"]:
                    counters["links_created"] += 1
                    conf = (preview.get("match") or {}).get("confidence") or 0
                    if conf >= 90:
                        counters["secure_relations"] = counters.get("secure_relations", 0) + 1
                    elif conf >= 50:
                        counters["suggested_relations"] = counters.get("suggested_relations", 0) + 1
                    else:
                        counters["ambiguous_relations"] = counters.get("ambiguous_relations", 0) + 1
                elif preview["would_update"]:
                    counters["links_updated"] += 1
            else:
                link = Trace.get_or_create_link_for_purchase_line(line)
                if existed:
                    counters["links_updated"] += 1
                else:
                    counters["links_created"] += 1
                conf = getattr(link, "confidence", 0) or 0
                if conf >= 90:
                    counters["secure_relations"] = counters.get("secure_relations", 0) + 1
                elif conf >= 50:
                    counters["suggested_relations"] = counters.get("suggested_relations", 0) + 1
                else:
                    counters["ambiguous_relations"] = counters.get("ambiguous_relations", 0) + 1

        bill_lines = self.env["account.move.line"].search(
            [
                ("company_id", "in", companies.ids),
                ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ("move_id.state", "=", "posted"),
                ("move_id.invoice_date", ">=", self.date_from),
                ("move_id.invoice_date", "<=", self.date_to),
                ("purchase_line_id", "!=", False),
                ("display_type", "=", False),
            ],
            limit=self._search_limit(),
        )
        Allocation = self.env["purchase.sale.cost.allocation"]
        for bill_line in bill_lines:
            counters["scanned_bill_lines"] += 1
            existing = Allocation.search(
                [("vendor_bill_line_id", "=", bill_line.id)], limit=1
            )
            if existing and existing.is_manual and existing.state == "confirmed":
                counters["skipped_manual_locked"] += 1
                continue
            if self.dry_run:
                preview = Trace.preview_allocation_for_bill_line(bill_line)
                if preview.get("locked"):
                    counters["skipped_manual_locked"] += 1
                elif preview.get("vals"):
                    if preview["exists"]:
                        counters["allocations_updated"] += 1
                    else:
                        counters["allocations_created"] += 1
            else:
                existed = bool(existing)
                Trace.create_suggested_allocation(bill_line)
                if existed:
                    counters["allocations_updated"] += 1
                else:
                    counters["allocations_created"] += 1
        return po_lines, bill_lines

    def _detect_transactions(self, companies, counters):
        Sale = super()._detect_transactions(companies, counters)
        self._backfill_customer_invoices(companies, counters)
        self._backfill_purchase_without_sale(companies, counters)
        self._backfill_vendor_bill_auxiliaries(companies, counters)
        self._enrich_transactions_from_links(companies, counters)
        return Sale

    def _backfill_customer_invoices(self, companies, counters):
        invoices = self.env["account.move"].search(
            [
                ("company_id", "in", companies.ids),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("invoice_date", ">=", self.date_from),
                ("invoice_date", "<=", self.date_to),
            ],
            limit=self._search_limit(),
        )
        counters["scanned_customer_invoices"] = len(invoices)
        Transaction = self.env["purchase.sale.margin.transaction"]
        for inv in invoices:
            related_so = inv.invoice_line_ids.mapped("sale_line_ids.order_id")
            existing = Transaction.find_canonical_for_sale(related_so[:1]) if related_so else Transaction.search(
                [("is_merged", "=", False), ("customer_invoice_ids", "in", inv.id)], limit=1
            )
            if self.dry_run:
                if not existing:
                    counters["transactions_created"] += 1
                else:
                    counters["transactions_updated"] += 1
                continue
            Transaction.find_or_create_canonical_transaction(
                sale_order=related_so[:1] if related_so else None,
                customer_invoice=inv,
                vals={
                    "company_id": inv.company_id.id,
                    "transaction_date": inv.invoice_date or self.date_from,
                    "source": "backfill",
                    "state": "detected",
                },
            )
            counters["transactions_updated" if existing else "transactions_created"] += 1

    def _backfill_purchase_without_sale(self, companies, counters):
        Purchase = self.env["purchase.order"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "in", ("purchase", "done")),
                ("date_order", ">=", self.date_from),
                ("date_order", "<=", self.date_to),
            ],
            limit=self._search_limit(),
        )
        Transaction = self.env["purchase.sale.margin.transaction"]
        Link = self.env["purchase.sale.cost.link"]
        for po in Purchase:
            has_sale_bridge = any(po.order_line.filtered(lambda l: l.sale_line_id))
            has_link = Link.search_count(
                [("purchase_id", "=", po.id), ("sale_id", "!=", False), ("state", "!=", "cancelled")]
            )
            existing = Transaction.search([("purchase_order_ids", "in", po.id)], limit=1)
            if has_sale_bridge or has_link:
                if self.dry_run:
                    if not existing:
                        counters["transactions_created"] += 1
                    continue
                sale_orders = po.order_line.mapped("sale_line_id.order_id")
                if not sale_orders:
                    sale_orders = Link.search(
                        [("purchase_id", "=", po.id), ("sale_id", "!=", False)]
                    ).mapped("sale_id")
                so = sale_orders[:1]
                canonical = Transaction.find_canonical_for_sale(so) if so else existing
                if canonical or so:
                    Transaction.find_or_create_canonical_transaction(
                        sale_order=so or None,
                        vals={
                            "company_id": po.company_id.id,
                            "name": so.name if so else po.name,
                            "purchase_order_ids": [(4, po.id)],
                            "sale_order_ids": [(4, s.id) for s in sale_orders],
                            "supplier_ids": [(4, po.partner_id.id)] if po.partner_id else False,
                            "transaction_date": po.date_order and po.date_order.date() or self.date_from,
                            "source": "backfill",
                            "state": "detected",
                            "confidence": 95 if has_sale_bridge else 70,
                        },
                    )
                    counters["transactions_updated" if canonical else "transactions_created"] += 1
                elif existing:
                    existing.write({"purchase_order_ids": [(4, po.id)]})
                    counters["transactions_updated"] += 1
                else:
                    Transaction.with_context(skip_canonical_reuse=True).create(
                        {
                            "company_id": po.company_id.id,
                            "name": po.name,
                            "purchase_order_ids": [(6, 0, [po.id])],
                            "supplier_ids": [(6, 0, [po.partner_id.id])],
                            "transaction_type": "resale",
                            "transaction_date": po.date_order and po.date_order.date() or self.date_from,
                            "source": "backfill",
                            "state": "detected",
                            "confidence": 95 if has_sale_bridge else 70,
                        }
                    )
                    counters["transactions_created"] += 1
                continue

            # Compra sin venta → operación de costo pendiente
            if existing:
                continue
            if self.dry_run:
                counters["transactions_created"] += 1
                counters["purchases_without_sale_count"] += 1
                continue
            usage = "inventory"
            if all(
                (l.cost_usage_type == "administrative_expense")
                for l in po.order_line.filtered(lambda x: not x.display_type)
            ) and po.order_line:
                usage = "administrative"
            Transaction.create(
                {
                    "company_id": po.company_id.id,
                    "name": po.name,
                    "purchase_order_ids": [(6, 0, [po.id])],
                    "supplier_ids": [(6, 0, [po.partner_id.id])],
                    "transaction_type": usage,
                    "transaction_date": po.date_order and po.date_order.date() or self.date_from,
                    "source": "backfill",
                    "state": "detected",
                }
            )
            counters["transactions_created"] += 1
            counters["purchases_without_sale_count"] += 1

    def _backfill_vendor_bill_auxiliaries(self, companies, counters):
        bills = self.env["account.move"].search(
            [
                ("company_id", "in", companies.ids),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("invoice_date", ">=", self.date_from),
                ("invoice_date", "<=", self.date_to),
            ],
            limit=self._search_limit(),
        )
        counters["scanned_vendor_bills"] = len(bills)
        Aux = self.env["purchase.sale.payable.auxiliary"]
        Transaction = self.env["purchase.sale.margin.transaction"]
        for bill in bills:
            existing = Aux.search([("vendor_bill_id", "=", bill.id)], limit=1)
            if self.dry_run:
                if not existing:
                    counters["auxiliaries_created"] = counters.get("auxiliaries_created", 0) + 1
                continue
            if not existing:
                existing = Aux.create(
                    {
                        "company_id": bill.company_id.id,
                        "vendor_bill_id": bill.id,
                    }
                )
                counters["auxiliaries_created"] = counters.get("auxiliaries_created", 0) + 1
            # Attach to transactions that already reference the PO/bill.
            # Sprint 6: a vendor bill belongs to at most ONE transaction.
            pos = bill.invoice_line_ids.mapped("purchase_line_id.order_id")
            txs = Transaction.search(
                ["|", ("vendor_bill_ids", "in", bill.id), ("purchase_order_ids", "in", pos.ids)]
            )
            already = Transaction.search([("vendor_bill_ids", "in", bill.id)], limit=1)
            if already:
                existing.write(
                    {
                        "transaction_ids": [(4, already.id)],
                        "sale_order_ids": [(4, so.id) for so in already.sale_order_ids],
                        "customer_invoice_ids": [
                            (4, inv.id) for inv in already.customer_invoice_ids
                        ],
                    }
                )
            elif txs:
                preferred = txs[:1]
                preferred.write({"vendor_bill_ids": [(4, bill.id)]})
                existing.write(
                    {
                        "transaction_ids": [(4, preferred.id)],
                        "sale_order_ids": [(4, so.id) for so in preferred.sale_order_ids],
                        "customer_invoice_ids": [
                            (4, inv.id) for inv in preferred.customer_invoice_ids
                        ],
                    }
                )

    def _enrich_transactions_from_links(self, companies, counters):
        if self.dry_run:
            return
        Link = self.env["purchase.sale.cost.link"]
        Transaction = self.env["purchase.sale.margin.transaction"]
        links = Link.search(
            [
                ("company_id", "in", companies.ids),
                ("sale_id", "!=", False),
                ("purchase_id", "!=", False),
                ("state", "!=", "cancelled"),
            ],
            limit=self._search_limit(),
        )
        for link in links:
            tx = Transaction.search(
                [
                    "|",
                    ("sale_order_ids", "in", link.sale_id.id),
                    ("purchase_order_ids", "in", link.purchase_id.id),
                ],
                limit=1,
            )
            if not tx:
                continue
            tx.write(
                {
                    "sale_order_ids": [(4, link.sale_id.id)],
                    "purchase_order_ids": [(4, link.purchase_id.id)],
                    "customer_id": link.sale_id.partner_id.id,
                    "supplier_ids": [(4, link.purchase_id.partner_id.id)],
                }
            )
            tx._repair_zero_cost_lines()

    def action_run(self):
        self.ensure_one()
        for key in (
            "scanned_customer_invoices",
            "scanned_vendor_bills",
            "auxiliaries_created",
            "secure_relations",
            "suggested_relations",
            "ambiguous_relations",
        ):
            if key not in self._fields:
                continue
        Trace = self.env["purchase.sale.trace.engine"]
        companies = self._get_target_companies()
        counters = {
            "scanned_po_lines": 0,
            "scanned_bill_lines": 0,
            "scanned_sale_orders": 0,
            "scanned_customer_invoices": 0,
            "scanned_vendor_bills": 0,
            "links_created": 0,
            "links_updated": 0,
            "allocations_created": 0,
            "allocations_updated": 0,
            "skipped_manual_locked": 0,
            "transactions_created": 0,
            "transactions_updated": 0,
            "sales_without_cost_count": 0,
            "purchases_without_sale_count": 0,
            "admin_candidate_count": 0,
            "inventory_pending_count": 0,
            "auxiliaries_created": 0,
            "secure_relations": 0,
            "suggested_relations": 0,
            "ambiguous_relations": 0,
        }

        self._run_link_allocation_backfill(Trace, companies, counters)
        self._detect_transactions(companies, counters)

        summary = _(
            "Modo: %(mode)s | Año: %(year)s | Compañías: %(companies)s\n"
            "Líneas OC: %(scanned_po)s · Facturas proveedor (líneas): %(scanned_bill)s\n"
            "Órdenes venta: %(scanned_so)s · Facturas cliente: %(scanned_inv)s · Facturas proveedor: %(scanned_vb)s\n"
            "Links: +%(lc)s / ~%(lu)s · Asignaciones: +%(ac)s / ~%(au)s · Bloqueadas: %(locked)s\n"
            "Operaciones: +%(tc)s / ~%(tu)s (nunca aprobadas automáticamente)\n"
            "Auxiliares CxP creados: %(aux)s\n"
            "Ventas sin costo: %(swc)s · Compras sin venta: %(pws)s\n"
            "Relaciones seguras/sugeridas/ambiguas: %(sec)s / %(sug)s / %(amb)s\n"
            "Admin / inventario pendiente: %(adm)s / %(inv)s"
        ) % {
            "mode": _("Simulación") if self.dry_run else _("Aplicado"),
            "year": self.year,
            "companies": ", ".join(companies.mapped("name")),
            "scanned_po": counters["scanned_po_lines"],
            "scanned_bill": counters["scanned_bill_lines"],
            "scanned_so": counters["scanned_sale_orders"],
            "scanned_inv": counters["scanned_customer_invoices"],
            "scanned_vb": counters["scanned_vendor_bills"],
            "lc": counters["links_created"],
            "lu": counters["links_updated"],
            "ac": counters["allocations_created"],
            "au": counters["allocations_updated"],
            "locked": counters["skipped_manual_locked"],
            "tc": counters["transactions_created"],
            "tu": counters["transactions_updated"],
            "aux": counters["auxiliaries_created"],
            "swc": counters["sales_without_cost_count"],
            "pws": counters["purchases_without_sale_count"],
            "sec": counters["secure_relations"],
            "sug": counters["suggested_relations"],
            "amb": counters["ambiguous_relations"],
            "adm": counters["admin_candidate_count"],
            "inv": counters["inventory_pending_count"],
        }

        counters.update({"state": "done", "result_summary": summary})
        self.write(counters)
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.sale.backfill.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
