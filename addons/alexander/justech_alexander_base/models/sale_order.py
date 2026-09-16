from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.client_order_ref and not vals.get("ref"):
            vals["ref"] = self.client_order_ref
        return vals
