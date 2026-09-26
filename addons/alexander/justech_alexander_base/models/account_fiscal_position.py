from odoo import api, models
from odoo.exceptions import ValidationError

from .account_tax import _CROSS_COMPANY_TAX_MSG


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    @api.constrains("tax_ids", "company_id")
    def _dx_check_fiscal_position_tax_company(self):
        for position in self:
            company = position.company_id
            if not company or not position.tax_ids:
                continue
            bad = position.sudo().tax_ids.filtered(
                lambda tax: tax.company_id and tax.company_id != company
            )
            if bad:
                raise ValidationError(_CROSS_COMPANY_TAX_MSG)
