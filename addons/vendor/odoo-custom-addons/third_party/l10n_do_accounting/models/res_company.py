# -*- coding: utf-8 -*-

from odoo import fields, models
from datetime import date


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_do_country_code = fields.Char(related="country_id.code", string="Country Code")
    l10n_do_dgii_start_date = fields.Date("Activities Start Date")

    l10n_do_default_client = fields.Selection(
        selection=[("non_payer", "Final Consumer"), ("taxpayer", "Fiscal Consumer")],
        default=lambda self: self._context.get("l10n_do_default_client", "taxpayer"),
        string="Default Customer",
    )
    l10n_do_ecf_issuer = fields.Boolean(
        "Is e-CF issuer",
        help="When activating this field, NCF issuance is disabled.",
    )
    l10n_do_ecf_deferred_submissions = fields.Boolean(
        "Deferred submissions",
        help="Identify taxpayers who have been previously authorized "
        "to have sales through offline mobile devices such as "
        "sales with Handheld, enter others.",
    )
    
    # Define la fecha de vencimiento del NCF para el próximo año
    l10n_do_ncf_exp_date = fields.Date(
        string="NCF Expiration date",
        default=lambda self: date.today().replace(year=date.today().year + 1, month=12, day=31),
    )

    def _localization_use_documents(self):
        """ Dominican localization uses documents """
        self.ensure_one()
        
        return (
            True
            if self.country_id == self.env.ref("base.do")
            else False
        )
