# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """Ensure Adel cannot auto-assign after Justech assignment.

        Adel's _post consumes fiscal sequences when l10n_latam_use_documents.
        We clear the Adel fiscal sequence link for Justech-enabled companies
        before the Adel branch runs (defense in depth with journal freeze).
        """
        for move in self:
            company = move.company_id
            if not company or not getattr(company, "justech_do_fiscal_enabled", False):
                continue
            if "l10n_do_fiscal_sequence_id" in move._fields and move.l10n_do_fiscal_sequence_id:
                move.l10n_do_fiscal_sequence_id = False
        return super()._post(soft=soft)
