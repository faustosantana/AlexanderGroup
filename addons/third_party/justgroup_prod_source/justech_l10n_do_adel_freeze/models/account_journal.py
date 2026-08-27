# -*- coding: utf-8 -*-
from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for journal in records:
            company = journal.company_id
            if (
                company
                and getattr(company, "justech_do_fiscal_enabled", False)
                and journal.l10n_latam_use_documents
            ):
                journal.l10n_latam_use_documents = False
        return records

    def write(self, vals):
        res = super().write(vals)
        if "l10n_latam_use_documents" in vals and vals.get("l10n_latam_use_documents"):
            to_fix = self.filtered(
                lambda j: j.company_id
                and getattr(j.company_id, "justech_do_fiscal_enabled", False)
                and j.l10n_latam_use_documents
            )
            if to_fix:
                # Prevent re-enabling Adel documents on Justech companies.
                super(AccountJournal, to_fix).write(
                    {"l10n_latam_use_documents": False}
                )
        return res
