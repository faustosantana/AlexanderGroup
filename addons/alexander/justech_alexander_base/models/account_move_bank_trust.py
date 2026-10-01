"""Antes de _post nativo, confía la cuenta de la compañía en facturas inbound."""

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _dx_trust_inbound_company_banks(self):
        banks = self.filtered(
            lambda move: move.is_inbound() and move.partner_bank_id
        ).mapped("partner_bank_id")
        if banks:
            banks._dx_trust_if_company_owned()

    def _post(self, soft=True):
        self._dx_trust_inbound_company_banks()
        return super()._post(soft=soft)
