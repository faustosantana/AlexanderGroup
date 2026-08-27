# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    justech_warranty_default_terms = fields.Text(
        related="company_id.justech_warranty_default_terms",
        readonly=False,
        string="Términos de garantía por defecto",
    )
    justech_warranty_reminder_days = fields.Integer(
        related="company_id.justech_warranty_reminder_days",
        readonly=False,
        string="Días de aviso previo al vencimiento",
    )
