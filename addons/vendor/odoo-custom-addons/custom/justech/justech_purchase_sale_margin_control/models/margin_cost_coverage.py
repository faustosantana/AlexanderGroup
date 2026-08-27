# -*- coding: utf-8 -*-
"""19.0.8.29.19 — Sale-line cost coverage vs Trace qty.assignment (provisional margin)."""
from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare
from markupsafe import escape, Markup

from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)

COST_COVERAGE_STATES = [
    ("complete", "Completa"),
    ("partial", "Parcial"),
    ("none", "Sin costos"),
    ("n_a", "N/A"),
]


class PurchaseSaleMarginTransactionCostCoverage(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    cost_coverage_state = fields.Selection(
        COST_COVERAGE_STATES,
        string="Cobertura de costos",
        compute="_compute_sale_cost_coverage",
        help="Completa solo cuando toda la cantidad vendida/facturada tiene qty.assignment.",
    )
    margin_is_provisional = fields.Boolean(
        string="Margen provisional",
        compute="_compute_sale_cost_coverage",
    )
    cost_related_sale_qty = fields.Float(
        string="Cant. venta con costo",
        compute="_compute_sale_cost_coverage",
        digits="Product Unit of Measure",
    )
    cost_pending_sale_qty = fields.Float(
        string="Cant. venta sin costo",
        compute="_compute_sale_cost_coverage",
        digits="Product Unit of Measure",
    )
    cost_pending_line_html = fields.Html(
        string="Pendientes de relacionar",
        compute="_compute_sale_cost_coverage",
        sanitize=False,
    )
    provisional_margin_banner = fields.Char(
        string="Aviso margen provisional",
        compute="_compute_sale_cost_coverage",
    )

    @api.depends(
        "sale_order_ids",
        "sale_order_ids.order_line.product_uom_qty",
        "sale_order_ids.order_line.qty_invoiced",
        "customer_invoice_ids",
        "customer_invoice_ids.state",
        "customer_invoice_ids.invoice_line_ids.quantity",
        "purchase_order_ids",
        "line_ids.quantity",
        "line_ids.line_type",
        "line_ids.data_origin",
        # Do NOT depend on display_sale_amount / display_cost_amount:
        # those fields are groups-restricted (Márgenes ver) and break web
        # form load for commercial users (Owl undefined / AccessError).
        "has_related_sale",
    )
    def _compute_sale_cost_coverage(self):
        svc = LineAllocationService(self.env)
        for rec in self:
            rows = svc.analyze_transaction_sale_cost_coverage(rec)
            total_sold = sum(r["sold_qty"] for r in rows)
            total_covered = sum(r["assigned_qty"] for r in rows)
            total_pending = sum(r["pending_qty"] for r in rows)
            rec.cost_related_sale_qty = total_covered
            rec.cost_pending_sale_qty = total_pending
            if not rows:
                rec.cost_coverage_state = "n_a"
                rec.margin_is_provisional = False
                rec.cost_pending_line_html = False
                rec.provisional_margin_banner = False
                continue
            if float_compare(total_pending, 0.0, precision_digits=4) <= 0:
                state = "complete"
            elif float_compare(total_covered, 0.0, precision_digits=4) <= 0:
                state = "none"
            else:
                state = "partial"
            rec.cost_coverage_state = state
            provisional = state in ("partial", "none") and bool(rec.has_related_sale)
            rec.margin_is_provisional = provisional
            pending_rows = [r for r in rows if float_compare(r["pending_qty"], 0.0, precision_digits=4) > 0]
            if pending_rows:
                body_parts = []
                for r in pending_rows:
                    st = (
                        _("SIN COSTO")
                        if float_compare(r["assigned_qty"], 0.0, precision_digits=4) <= 0
                        else _("PENDIENTE DE CUBRIR")
                    )
                    body_parts.append(
                        Markup(
                            "<tr class='text-danger'>"
                            "<td>%s</td><td>%s</td>"
                            "<td>%.2f</td><td>%.2f</td><td>%.2f</td><td>%.2f</td>"
                            "<td>%s</td></tr>"
                        )
                        % (
                            escape(r["product_name"] or ""),
                            escape(r["sale_doc"] or ""),
                            r["sold_qty"],
                            r.get("purchase_qty", r["assigned_qty"]),
                            r.get("historical_qty", 0.0),
                            r["pending_qty"],
                            escape(str(st)),
                        )
                    )
                rec.cost_pending_line_html = Markup(
                    "<table class='table table-sm o_list_table'>"
                    "<thead><tr>"
                    "<th>Producto</th><th>Documento venta</th>"
                    "<th>Vendido</th><th>Compra</th><th>Histórico</th><th>Pendiente</th><th>Estado</th>"
                    "</tr></thead><tbody>%s</tbody></table>"
                ) % Markup("").join(body_parts)
            else:
                rec.cost_pending_line_html = False
            if provisional:
                rec.provisional_margin_banner = _(
                    "Faltan costos por relacionar. El margen mostrado es provisional "
                    "y no representa todavía el margen real de la operación."
                )
            else:
                rec.provisional_margin_banner = False

    def _compute_margin_band(self):
        # Live ASG coverage: never classify provisional margins as healthy/low/negative.
        # Keep parent @api.depends — do not redeclare (avoids field_computed warnings).
        super()._compute_margin_band()
        svc = LineAllocationService(self.env)
        for rec in self:
            if not rec.has_related_sale:
                continue
            rows = svc.analyze_transaction_sale_cost_coverage(rec)
            if not rows:
                continue
            pending = sum(r["pending_qty"] for r in rows)
            if float_compare(pending, 0.0, precision_digits=4) > 0 and rec.margin_band in (
                "healthy",
                "low",
                "negative",
            ):
                rec.margin_band = "pending"

    def action_relate_purchases(self):
        """Canonical multi-vendor Relacionar compras (engine)."""
        self.ensure_one()
        ctx = {
            "default_company_id": self.company_id.id,
            "default_customer_id": self.customer_id.id if self.customer_id else False,
            "default_sale_order_ids": [(6, 0, self.sale_order_ids.ids)],
            "default_customer_invoice_ids": [(6, 0, self.customer_invoice_ids.ids)],
            "default_purchase_order_ids": [(6, 0, self.purchase_order_ids.ids)],
            "default_vendor_bill_ids": [(6, 0, self.vendor_bill_ids.ids)],
            "default_salesperson_id": self.salesperson_id.id if self.salesperson_id else False,
            # Prefill existing suppliers without replacing on confirm (append)
            "default_supplier_ids": [(6, 0, self.supplier_ids.ids)],
        }
        if self.supplier_ids[:1]:
            ctx["default_supplier_id"] = self.supplier_ids[:1].id
            ctx["default_active_supplier_id"] = self.supplier_ids[:1].id
        return {
            "type": "ir.actions.act_window",
            "name": _("Relacionar compras"),
            "res_model": "purchase.sale.create.transaction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    def action_manage_purchases(self):
        """Visible UX hub on MTX — pre-create so ARTÍCULOS render immediately."""
        self.ensure_one()
        ctx = {
            "active_id": self.id,
            "active_ids": [self.id],
            "active_model": "purchase.sale.margin.transaction",
            "default_transaction_id": self.id,
            "default_company_id": self.company_id.id,
            "default_sale_order_ids": [(6, 0, self.sale_order_ids.ids)],
            "default_customer_invoice_ids": [(6, 0, self.customer_invoice_ids.ids)],
        }
        wiz = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(**ctx)
            .create({})
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar compras"),
            "res_model": "purchase.sale.manage.purchases.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": ctx,
        }

    def action_add_purchase_orders(self):
        """Redirect legacy button to hub (engine remains action_relate_purchases)."""
        return self.action_manage_purchases()
