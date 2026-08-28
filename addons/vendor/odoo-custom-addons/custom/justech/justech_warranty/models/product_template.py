# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    warranty_months = fields.Integer(
        string="Meses de garantía",
        default=0,
        help="Duración de la garantía en meses. Si es mayor que 0, al validar la "
        "factura de cliente se generará una garantía para este producto.",
    )
    has_warranty = fields.Boolean(
        string="Con garantía",
        compute="_compute_has_warranty",
        store=True,
    )

    @api.depends("warranty_months")
    def _compute_has_warranty(self):
        for template in self:
            template.has_warranty = template.warranty_months > 0


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_warranty_months(self):
        self.ensure_one()
        return self.product_tmpl_id.warranty_months or 0
