# -*- coding: utf-8 -*-
"""Compatibilidad: el botón legacy 'Crear Orden de Compra' redirige al wizard nuevo."""
from odoo import _, api, models


class CreatePurchaseOrderCompat(models.TransientModel):
    _inherit = "create.purchaseorder"

    def action_create_purchase_order(self):
        """Redirect legacy bi_convert confirm to pending-aware flow.

        Kept so old action XML still works; users should prefer Comprar pendientes.
        """
        so = self.env["sale.order"].browse(self.env.context.get("active_id"))
        if not so:
            return super().action_create_purchase_order()
        # Open new wizard instead of creating uncontrolled PO
        return so.action_justech_buy_pending()

    @api.model
    def default_get(self, fields_list):
        # Still load for display if someone opens old wizard, but prefer redirect
        return super().default_get(fields_list)


class SaleOrderBiConvertCompat(models.Model):
    _inherit = "sale.order"

    def action_justech_legacy_create_po(self):
        """Alias used if view still points to bi_convert action."""
        return self.action_justech_buy_pending()
