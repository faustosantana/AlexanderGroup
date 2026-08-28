# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    justech_purchase_count = fields.Integer(
        string="Compras",
        compute="_compute_justech_purchase_count",
    )
    justech_qty_pending_purchase = fields.Float(
        string="Pendiente comprar",
        compute="_compute_justech_purchase_totals",
    )
    justech_qty_pending_receive = fields.Float(
        string="Pendiente recibir",
        compute="_compute_justech_purchase_totals",
    )
    justech_qty_pending_deliver = fields.Float(
        string="Pendiente entregar",
        compute="_compute_justech_purchase_totals",
    )
    justech_supply_summary_html = fields.Html(
        string="Resumen abastecimiento",
        compute="_compute_justech_purchase_totals",
        sanitize=False,
    )

    def _justech_related_purchase_orders(self):
        """POs related by sale_line_id, assignments, or origin (display only)."""
        self.ensure_one()
        Purchase = self.env["purchase.order"]
        pols = self.order_line.mapped("purchase_line_ids").filtered(
            lambda l: l.state != "cancel"
        )
        assigns = self.env["justech.purchase.sale.qty.assignment"].search(
            [
                ("sale_order_id", "=", self.id),
                ("state", "=", "active"),
            ]
        )
        po_ids = set(pols.mapped("order_id").ids + assigns.mapped("purchase_order_id").ids)
        if self.name:
            origin_pos = Purchase.search(
                [
                    ("origin", "=", self.name),
                    ("company_id", "=", self.company_id.id),
                    ("state", "!=", "cancel"),
                ]
            )
            po_ids.update(origin_pos.ids)
        return Purchase.browse(list(po_ids))

    @api.depends(
        "order_line.purchase_line_ids",
        "order_line.purchase_line_ids.order_id",
        "order_line.justech_qty_assignment_ids",
        "name",
        "company_id",
    )
    def _compute_justech_purchase_count(self):
        for order in self:
            order.justech_purchase_count = len(order._justech_related_purchase_orders())

    @api.depends(
        "order_line.justech_qty_pending_purchase",
        "order_line.justech_qty_pending_receive",
        "order_line.justech_qty_pending_deliver",
        "order_line.justech_qty_sold",
        "order_line.justech_qty_stock_covered",
        "order_line.justech_qty_purchased",
        "order_line.justech_qty_received",
        "order_line.product_id",
        "order_line.display_type",
    )
    def _compute_justech_purchase_totals(self):
        for order in self:
            lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
            order.justech_qty_pending_purchase = sum(
                lines.mapped("justech_qty_pending_purchase")
            )
            order.justech_qty_pending_receive = sum(
                lines.mapped("justech_qty_pending_receive")
            )
            order.justech_qty_pending_deliver = sum(
                lines.mapped("justech_qty_pending_deliver")
            )
            rows = []
            for line in lines:
                rows.append(
                    "<tr>"
                    "<td>%s</td><td class='text-end'>%.2f</td>"
                    "<td class='text-end'>%.2f</td><td class='text-end'>%.2f</td>"
                    "<td class='text-end'>%.2f</td><td class='text-end'>%.2f</td>"
                    "<td class='text-end'>%.2f</td></tr>"
                    % (
                        line.product_id.display_name,
                        line.justech_qty_sold,
                        line.justech_qty_stock_covered,
                        line.justech_qty_purchased,
                        line.justech_qty_pending_purchase,
                        line.justech_qty_received,
                        line.justech_qty_pending_receive,
                    )
                )
            order.justech_supply_summary_html = (
                "<table class='table table-sm o_list_table'>"
                "<thead><tr>"
                "<th>Producto</th><th>Vendido</th><th>Stock</th><th>Comprado</th>"
                "<th>Falta comprar</th><th>Recibido</th><th>Falta recibir</th>"
                "</tr></thead><tbody>%s</tbody></table>" % "".join(rows)
            ) if rows else False

    def action_justech_buy_pending(self):
        if len(self) != 1 or not isinstance(self.id, int):
            raise UserError(
                _("Guarde la cotización antes de generar una Orden de Compra.")
            )
        return {
            "name": _("Generar orden de compra"),
            "type": "ir.actions.act_window",
            "res_model": "justech.buy.pending.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
                "active_id": self.id,
                "active_model": "sale.order",
            },
        }

    def action_justech_link_existing_po(self):
        if len(self) != 1 or not isinstance(self.id, int):
            raise UserError(
                _(
                    "Guarde la cotización antes de relacionar una compra existente."
                )
            )
        return {
            "name": _("Relacionar compra existente"),
            "type": "ir.actions.act_window",
            "res_model": "justech.link.existing.po.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_id": self.id,
                "active_id": self.id,
                "active_model": "sale.order",
            },
        }

    def action_justech_open_purchases(self):
        """Único smart button Compras: trazabilidad por línea (no el listado nativo)."""
        self.ensure_one()
        action = self.action_justech_open_purchase_coverage()
        action["name"] = _("Compras")
        return action

    def action_justech_open_purchase_coverage(self):
        """Coverage grid: open SOL list filtered to this SO with purchase fields."""
        self.ensure_one()
        return {
            "name": _("Abastecimiento"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order.line",
            "view_mode": "list,form",
            "views": [
                (
                    self.env.ref(
                        "justech_sale_purchase_trace.view_sale_order_line_purchase_coverage_list"
                    ).id,
                    "list",
                ),
                (
                    self.env.ref(
                        "justech_sale_purchase_trace.view_sale_order_line_purchase_coverage_form"
                    ).id,
                    "form",
                ),
            ],
            "domain": [
                ("order_id", "=", self.id),
                ("display_type", "=", False),
            ],
            "context": {
                "default_order_id": self.id,
                "create": False,
            },
        }

    # Keep legacy smart button working but prefer line-based domain
    def action_open_purchase_order(self):
        self.ensure_one()
        pos = self._justech_related_purchase_orders()
        tree_id = self.env.ref("purchase.purchase_order_kpis_tree").id
        form_id = self.env.ref("purchase.purchase_order_form").id
        return {
            "name": _("Compras"),
            "view_mode": "list,form",
            "views": [(tree_id, "list"), (form_id, "form")],
            "res_model": "purchase.order",
            "domain": [("id", "in", pos.ids)],
            "type": "ir.actions.act_window",
            "target": "current",
        }

    def _get_po(self):
        for orders in self:
            orders.po_count = len(orders._justech_related_purchase_orders())
