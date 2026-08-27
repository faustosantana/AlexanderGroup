"""Campos DGII 623 en pagos — sin dependencia Hellenia."""
from odoo import fields, models


class AccountPaymentGov623Fields(models.Model):
    _inherit = "account.payment"

    justech_do_gov_withholding_amount = fields.Float(
        string="Retención 5% Gobierno",
        digits=(16, 2),
        copy=False,
        help="Monto retenido por entidad del Estado en este pago.",
    )
