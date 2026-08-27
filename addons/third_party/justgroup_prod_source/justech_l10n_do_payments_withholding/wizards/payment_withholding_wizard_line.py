"""Línea transitoria de retención — wizard de pagos (Fase 2: preview company.config)."""
from __future__ import annotations

from odoo import fields, models


class JustechPaymentWithholdingWizardLine(models.TransientModel):
    _name = "justech.payment.withholding.wizard.line"
    _description = "Detalle retención transitorio — wizard pago"

    wizard_id = fields.Many2one("justech.payment.partner.wizard", ondelete="cascade")
    wizard_line_id = fields.Many2one("justech.payment.partner.wizard.line", ondelete="cascade")
    register_wizard_id = fields.Many2one("account.payment.register", ondelete="cascade")
    catalog_id = fields.Many2one("justech.do.withholding.catalog", string="Retención")
    company_id = fields.Many2one("res.company", string="Empresa", readonly=True)
    dgii_code = fields.Char(related="catalog_id.dgii_withholding_code", string="Código DGII", readonly=True)
    catalog_code = fields.Char(string="Código", readonly=True)
    tax_id = fields.Many2one("account.tax", string="Impuesto")
    label = fields.Char(string="Descripción")
    base_label = fields.Char(string="Tipo de base")
    base_amount = fields.Monetary(string="Base", currency_field="currency_id")
    rate = fields.Float(string="Porcentaje")
    amount = fields.Monetary(string="Monto retenido", currency_field="currency_id")
    account_id = fields.Many2one("account.account", string="Cuenta contable")
    account_code = fields.Char(string="Código cuenta", readonly=True)
    account_nature = fields.Char(string="Naturaleza", readonly=True)
    config_state = fields.Char(string="Estado", readonly=True)
    date_from = fields.Date(string="Vigente desde", readonly=True)
    date_to = fields.Date(string="Vigente hasta", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda")
    invoice_name = fields.Char(related="wizard_line_id.invoice_name", string="Factura")
