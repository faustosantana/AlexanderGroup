# -*- coding: utf-8 -*-
"""Bootstrap de configs de retención al crear empresa."""
from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        Catalog = self.env.get("justech.do.withholding.catalog")
        if Catalog is not None:
            Catalog.ensure_company_configs(companies=companies)
        return companies
