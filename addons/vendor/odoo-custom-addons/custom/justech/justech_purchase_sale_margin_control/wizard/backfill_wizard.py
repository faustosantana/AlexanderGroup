# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

BACKFILL_YEAR = 2026


class PurchaseSaleBackfillWizard(models.TransientModel):
    """Backfills purchase.sale.cost.link / purchase.sale.cost.allocation
    records for historical 2026 purchase order lines and vendor bill lines,
    and detects/creates purchase.sale.margin.transaction records.

    Audit rule: backfill is restricted to year 2026 only, must support a
    dry-run mode that performs zero database writes on business models, and
    NEVER creates a margin transaction beyond state 'detected'/'pending_review'
    (validation/approval always stays a manual human step)."""

    _name = "purchase.sale.backfill.wizard"
    _description = "Backfill de trazabilidad compra-venta 2026"

    year = fields.Integer(default=BACKFILL_YEAR, required=True)
    company_ids = fields.Many2many(
        "res.company", default=lambda self: self.env.company, string="Compañías"
    )
    dry_run = fields.Boolean(default=True, string="Simulación (dry-run)")
    batch_size = fields.Integer(default=200, string="Tamaño de lote")
    state = fields.Selection([("draft", "Borrador"), ("done", "Completado")], default="draft")

    date_from = fields.Date(compute="_compute_dates")
    date_to = fields.Date(compute="_compute_dates")

    scanned_po_lines = fields.Integer(readonly=True)
    scanned_bill_lines = fields.Integer(readonly=True)
    scanned_sale_orders = fields.Integer(readonly=True)
    links_created = fields.Integer(readonly=True)
    links_updated = fields.Integer(readonly=True)
    allocations_created = fields.Integer(readonly=True)
    allocations_updated = fields.Integer(readonly=True)
    skipped_manual_locked = fields.Integer(readonly=True)

    transactions_created = fields.Integer(readonly=True, string="Operaciones creadas")
    transactions_updated = fields.Integer(readonly=True, string="Operaciones actualizadas")
    sales_without_cost_count = fields.Integer(readonly=True, string="Ventas sin costo detectadas")
    purchases_without_sale_count = fields.Integer(readonly=True, string="Compras sin venta detectadas")
    admin_candidate_count = fields.Integer(readonly=True, string="Candidatos a gasto administrativo")
    inventory_pending_count = fields.Integer(readonly=True, string="Candidatos a inventario pendiente")

    result_summary = fields.Text(readonly=True)

    @api.depends("year")
    def _compute_dates(self):
        for rec in self:
            if rec.year:
                rec.date_from = fields.Date.to_date("%s-01-01" % rec.year)
                rec.date_to = fields.Date.to_date("%s-12-31" % rec.year)
            else:
                rec.date_from = False
                rec.date_to = False

    @api.constrains("year")
    def _check_year(self):
        for rec in self:
            if rec.year != BACKFILL_YEAR:
                raise ValidationError(
                    _("El backfill solo está autorizado para el año %s.") % BACKFILL_YEAR
                )

    def _get_target_companies(self):
        return self.company_ids or self.env.company

    # ------------------------------------------------------------------
    # Link / allocation backfill (unchanged behaviour from 1.x)
    # ------------------------------------------------------------------
    def _run_link_allocation_backfill(self, Trace, companies, counters):
        po_lines = self.env["purchase.order.line"].search(
            [
                ("company_id", "in", companies.ids),
                ("order_id.date_order", ">=", self.date_from),
                ("order_id.date_order", "<=", self.date_to),
                ("order_id.state", "in", ("purchase", "done")),
                ("display_type", "=", False),
            ],
            limit=self.batch_size or None,
        )
        Link = self.env["purchase.sale.cost.link"]
        for line in po_lines:
            counters["scanned_po_lines"] += 1
            existed = Link.search_count([("purchase_line_id", "=", line.id)])
            if self.dry_run:
                preview = Trace.preview_link_for_purchase_line(line)
                if not preview["exists"] and preview["match"]:
                    counters["links_created"] += 1
                elif preview["would_update"]:
                    counters["links_updated"] += 1
            else:
                Trace.get_or_create_link_for_purchase_line(line)
                if existed:
                    counters["links_updated"] += 1
                else:
                    counters["links_created"] += 1

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
            limit=self.batch_size or None,
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

    # ------------------------------------------------------------------
    # Margin transaction detection (2.0.0)
    # ------------------------------------------------------------------
    def _detect_transactions(self, companies, counters):
        Sale = self.env["sale.order"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "in", ("sale", "done")),
                ("date_order", ">=", self.date_from),
                ("date_order", "<=", self.date_to),
            ],
            limit=self.batch_size or None,
        )
        counters["scanned_sale_orders"] = len(Sale)
        Transaction = self.env["purchase.sale.margin.transaction"]

        for sale in Sale:
            cost_link_count = self.env["purchase.sale.cost.link"].search_count(
                [("sale_id", "=", sale.id), ("state", "!=", "cancelled")]
            )
            allocation_count = self.env["purchase.sale.cost.allocation"].search_count(
                [("sale_order_id", "=", sale.id), ("state", "not in", ("cancelled", "excluded"))]
            )
            has_cost = bool(cost_link_count or allocation_count)
            if not has_cost:
                counters["sales_without_cost_count"] += 1

            existing_tx = Transaction.find_canonical_for_sale(sale)
            if self.dry_run:
                if not existing_tx:
                    counters["transactions_created"] += 1
                else:
                    counters["transactions_updated"] += 1
                continue

            if existing_tx:
                if existing_tx.state in ("draft",):
                    existing_tx.write({"state": "detected"})
                existing_tx.write({"sale_order_ids": [(4, sale.id)]})
                counters["transactions_updated"] += 1
            else:
                Transaction.find_or_create_canonical_transaction(
                    sale_order=sale,
                    vals={
                        "company_id": sale.company_id.id,
                        "name": sale.name,
                        "transaction_date": sale.date_order and sale.date_order.date() or self.date_from,
                        "salesperson_id": sale.user_id.id,
                        "source": "backfill",
                        "state": "detected",
                    },
                )
                counters["transactions_created"] += 1

        # Purchase side classification candidates (admin / inventory / no sale).
        po_lines = self.env["purchase.order.line"].search(
            [
                ("company_id", "in", companies.ids),
                ("order_id.date_order", ">=", self.date_from),
                ("order_id.date_order", "<=", self.date_to),
                ("order_id.state", "in", ("purchase", "done")),
                ("display_type", "=", False),
            ],
            limit=self.batch_size or None,
        )
        for line in po_lines:
            if line.cost_usage_type == "administrative_expense":
                counters["admin_candidate_count"] += 1
            elif line.cost_usage_type == "inventory_pending":
                counters["inventory_pending_count"] += 1
            if not line.sale_line_id and line.cost_usage_type not in (
                "administrative_expense", "asset", "internal_service", "not_sales_related",
            ):
                has_link_to_sale = self.env["purchase.sale.cost.link"].search_count(
                    [("purchase_line_id", "=", line.id), ("sale_id", "!=", False), ("state", "!=", "cancelled")]
                )
                if not has_link_to_sale:
                    counters["purchases_without_sale_count"] += 1

        return Sale

    def action_run(self):
        self.ensure_one()
        Trace = self.env["purchase.sale.trace.engine"]
        companies = self._get_target_companies()
        counters = {
            "scanned_po_lines": 0,
            "scanned_bill_lines": 0,
            "scanned_sale_orders": 0,
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
        }

        self._run_link_allocation_backfill(Trace, companies, counters)
        self._detect_transactions(companies, counters)

        summary = _(
            "Modo: %(mode)s | Año: %(year)s | Compañías: %(companies)s\n"
            "Líneas de compra escaneadas: %(scanned_po)s (nuevos %(lc)s / actualizados %(lu)s)\n"
            "Líneas de factura escaneadas: %(scanned_bill)s (nuevas %(ac)s / actualizadas %(au)s)\n"
            "Bloqueadas (manual confirmada): %(locked)s\n"
            "Órdenes de venta escaneadas: %(scanned_so)s\n"
            "Operaciones de margen: %(tc)s nuevas / %(tu)s actualizadas (siempre en detectada/pendiente, nunca aprobadas)\n"
            "Ventas sin costo detectadas: %(swc)s | Compras sin venta detectadas: %(pws)s\n"
            "Candidatos a gasto administrativo: %(adm)s | Candidatos a inventario pendiente: %(inv)s"
        ) % {
            "mode": _("Simulación") if self.dry_run else _("Aplicado"),
            "year": self.year,
            "companies": ", ".join(companies.mapped("name")),
            "scanned_po": counters["scanned_po_lines"],
            "lc": counters["links_created"],
            "lu": counters["links_updated"],
            "scanned_bill": counters["scanned_bill_lines"],
            "ac": counters["allocations_created"],
            "au": counters["allocations_updated"],
            "locked": counters["skipped_manual_locked"],
            "scanned_so": counters["scanned_sale_orders"],
            "tc": counters["transactions_created"],
            "tu": counters["transactions_updated"],
            "swc": counters["sales_without_cost_count"],
            "pws": counters["purchases_without_sale_count"],
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
