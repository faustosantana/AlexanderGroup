# -*- coding: utf-8 -*-
"""Evita que bi_convert copie el nombre de la cotización en partner_ref."""
from odoo import models


class CreatePurchaseOrder(models.TransientModel):
    _inherit = "create.purchaseorder"

    def action_create_purchase_order(self):
        purchase_order = super().action_create_purchase_order()
        # partner_ref debe quedar para la referencia real del proveedor.
        so = self.env["sale.order"].browse(self.env.context.get("active_id"))
        if (
            purchase_order
            and so
            and purchase_order.partner_ref
            and purchase_order.partner_ref == so.name
        ):
            purchase_order.partner_ref = False
        # Completar sale_line_id cuando el mapeo producto→línea SO es inequívoco.
        if purchase_order and so and "sale_line_id" in purchase_order.order_line._fields:
            for pol in purchase_order.order_line.filtered(
                lambda l: not l.display_type and l.product_id and not l.sale_line_id
            ):
                sols = so.order_line.filtered(
                    lambda l: not l.display_type and l.product_id == pol.product_id
                )
                if len(sols) == 1:
                    pol.sale_line_id = sols.id
        return purchase_order
