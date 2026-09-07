from odoo import models
from odoo.exceptions import AccessError


class ApprovalStateWriteGuard(models.AbstractModel):
    _name = "justech.alexander.approval.state.guard"
    _description = "Bloquea justech_approval_state sin sudo"

    def write(self, vals):
        if "justech_approval_state" in vals and not self.env.su:
            raise AccessError(
                "No puede marcar un documento como aprobado de forma directa."
            )
        return super().write(vals)


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "justech.alexander.approval.state.guard"]


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "justech.alexander.approval.state.guard"]


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "justech.alexander.approval.state.guard"]
