# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class AccountFiscalSequence(models.Model):
    _inherit = "account.fiscal.sequence"

    def get_fiscal_number(self):
        """Block Adel sequence consumption when Justech fiscal motor is on."""
        for seq in self:
            company = seq.company_id
            if company and getattr(company, "justech_do_fiscal_enabled", False):
                raise UserError(
                    _(
                        "Motor Adel congelado: la empresa %(company)s usa el motor "
                        "fiscal Justech. No se pueden consumir secuencias Adel. "
                        "Asigne NCF únicamente vía Justech.",
                        company=company.display_name,
                    )
                )
        return super().get_fiscal_number()
