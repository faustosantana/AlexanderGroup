# -*- coding: utf-8 -*-
from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_sale_orders(self):
        """Prefer line-level sale_line_id / qty assignments over origin string."""
        self.ensure_one()
        sos = self.order_line.mapped("sale_line_id.order_id")
        assigns = self.env["justech.purchase.sale.qty.assignment"].search(
            [
                ("purchase_order_id", "=", self.id),
                ("state", "=", "active"),
            ]
        )
        sos |= assigns.mapped("sale_order_id")
        if sos:
            return sos
        parent = super()
        if hasattr(parent, "_get_sale_orders"):
            sos = parent._get_sale_orders()
            if sos:
                return sos
        if self.origin:
            return self.env["sale.order"].search(
                [
                    ("name", "=", self.origin),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=5,
            )
        return self.env["sale.order"]

    def button_cancel(self):
        res = super().button_cancel()
        # Cancel commercial assignments so pending purchase is restored
        assigns = self.env["justech.purchase.sale.qty.assignment"].search(
            [
                ("purchase_order_id", "in", self.ids),
                ("state", "=", "active"),
            ]
        )
        if assigns:
            assigns.write({"state": "cancelled"})
        # Invalidate SOL coverage
        sols = self.order_line.mapped("sale_line_id") | assigns.mapped("sale_line_id")
        if sols:
            sols.invalidate_recordset()
        return res
