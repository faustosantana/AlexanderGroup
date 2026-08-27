# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    justech_related_purchase_count = fields.Integer(
        compute="_compute_justech_invoice_purchase_trace",
    )
    justech_invoice_pending_purchase = fields.Float(
        compute="_compute_justech_invoice_purchase_trace",
    )

    def _justech_invoice_sale_lines(self):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            return self.env["sale.order.line"]
        return self.invoice_line_ids.mapped("sale_line_ids")

    @api.depends(
        "move_type",
        "invoice_line_ids.sale_line_ids",
        "invoice_line_ids.sale_line_ids.purchase_line_ids",
        "invoice_line_ids.sale_line_ids.justech_qty_pending_purchase",
    )
    def _compute_justech_invoice_purchase_trace(self):
        for move in self:
            sols = move._justech_invoice_sale_lines()
            pos = sols.mapped("purchase_line_ids.order_id")
            assigns = self.env["justech.purchase.sale.qty.assignment"].search(
                [("sale_line_id", "in", sols.ids), ("state", "=", "active")]
            )
            pos |= assigns.mapped("purchase_order_id")
            move.justech_related_purchase_count = len(pos)
            move.justech_invoice_pending_purchase = sum(
                sols.mapped("justech_qty_pending_purchase")
            )

    def action_justech_invoice_related_purchases(self):
        self.ensure_one()
        sols = self._justech_invoice_sale_lines()
        if not sols:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sin trazabilidad a venta"),
                    "message": _(
                        "Esta factura no tiene líneas vinculadas a órdenes de venta. "
                        "No se crea vínculo automático con compras."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }
        return {
            "name": _("Compras relacionadas"),
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
            "domain": [("id", "in", sols.ids)],
            "context": {"create": False},
        }

    def action_justech_invoice_buy_pending(self):
        self.ensure_one()
        sols = self._justech_invoice_sale_lines()
        if not sols:
            return self.action_justech_invoice_related_purchases()
        orders = sols.mapped("order_id")
        if len(orders) == 1:
            return orders.action_justech_buy_pending()
        # Multi-SO invoice: open coverage grouped view
        return {
            "name": _("Generar orden de compra (por venta)"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order.line",
            "view_mode": "list",
            "views": [
                (
                    self.env.ref(
                        "justech_sale_purchase_trace.view_sale_order_line_purchase_coverage_list"
                    ).id,
                    "list",
                )
            ],
            "domain": [("id", "in", sols.ids)],
            "context": {"create": False},
        }

    def action_justech_invoice_link_existing_po(self):
        self.ensure_one()
        sols = self._justech_invoice_sale_lines()
        if not sols:
            return self.action_justech_invoice_related_purchases()
        orders = sols.mapped("order_id")
        # Prefer first SO; user can open others from coverage
        return orders[:1].action_justech_link_existing_po()
