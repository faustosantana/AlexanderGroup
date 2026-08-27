# -*- coding: utf-8 -*-
"""UX Compras — Cotización de referencia y etiquetas (sin lógica fiscal)."""
from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    justech_reference_sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotización de referencia",
        compute="_compute_justech_reference_sale_orders",
        readonly=True,
        help="Cotización/Pedido de venta origen. Relación inequívoca vía "
        "sale_line_id o, en conversiones bi_convert, origin → sale.order "
        "de la misma empresa. No reutiliza partner_ref.",
    )
    justech_reference_sale_order_ids = fields.Many2many(
        "sale.order",
        string="Cotizaciones de referencia",
        compute="_compute_justech_reference_sale_orders",
        readonly=True,
    )
    justech_reference_sale_order_count = fields.Integer(
        string="Nº cotizaciones de referencia",
        compute="_compute_justech_reference_sale_orders",
    )

    def _justech_sales_from_lines(self):
        self.ensure_one()
        if hasattr(self, "_get_sale_orders"):
            sales = self._get_sale_orders()
            if sales:
                return sales
        if "sale_order_id" in self.order_line._fields:
            return self.order_line.mapped("sale_order_id")
        if "sale_line_id" in self.order_line._fields:
            return self.order_line.mapped("sale_line_id.order_id")
        return self.env["sale.order"]

    def _justech_sales_from_bi_convert_origin(self):
        """Relación inequívoca bi_convert: origin = sale.order.name (misma empresa).

        No usa partner_ref. Exige exactamente un match en la misma compañía.
        """
        self.ensure_one()
        origin = (self.origin or "").strip()
        if not origin or not self.company_id:
            return self.env["sale.order"]
        return self.env["sale.order"].sudo().search(
            [
                ("name", "=", origin),
                ("company_id", "=", self.company_id.id),
            ],
            limit=2,
        )

    @api.depends(
        "company_id",
        "origin",
        "order_line.sale_line_id",
        "order_line.sale_order_id",
    )
    def _compute_justech_reference_sale_orders(self):
        Sale = self.env["sale.order"]
        for order in self:
            sales = order._justech_sales_from_lines()
            if not sales:
                bi = order._justech_sales_from_bi_convert_origin()
                sales = bi if len(bi) == 1 else Sale
            # Misma empresa únicamente (bloquear cruces).
            if order.company_id:
                sales = sales.filtered(lambda s: s.company_id == order.company_id)
            sales = Sale.browse(sales.ids)
            order.justech_reference_sale_order_ids = sales
            order.justech_reference_sale_order_count = len(sales)
            order.justech_reference_sale_order_id = sales[:1] if len(sales) == 1 else False

    def action_open_justech_reference_sale_orders(self):
        self.ensure_one()
        sales = self.justech_reference_sale_order_ids
        if not sales and self.justech_reference_sale_order_id:
            sales = self.justech_reference_sale_order_id
        action = {
            "type": "ir.actions.act_window",
            "name": _("Cotizaciones de referencia"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", sales.ids)],
            "context": {
                "default_company_id": self.company_id.id,
                "allowed_company_ids": [self.company_id.id],
            },
        }
        if len(sales) == 1:
            action.update({"view_mode": "form", "res_id": sales.id})
        return action

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Solo etiquetas UX: no cambia claves técnicas de estado."""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        if "state" in res and res["state"].get("selection"):
            label_map = {
                "draft": _("Solicitud de Orden"),
                "sent": _("Solicitud de Orden enviada"),
            }
            res["state"]["selection"] = [
                (key, label_map.get(key, label))
                for key, label in res["state"]["selection"]
            ]
        if "partner_ref" in res:
            res["partner_ref"]["string"] = _("Referencia del proveedor")
        return res
