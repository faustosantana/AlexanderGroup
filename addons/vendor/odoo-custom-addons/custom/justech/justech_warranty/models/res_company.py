# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    justech_warranty_default_terms = fields.Text(
        string="Términos de garantía por defecto",
        help="Se aplican a las garantías nuevas cuando no se indican términos específicos.",
    )
    justech_warranty_reminder_days = fields.Integer(
        string="Días de aviso previo al vencimiento",
        default=30,
        help="Antelación (en días) para alertas de vencimiento de garantías (Fase 2).",
    )
