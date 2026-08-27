# -*- coding: utf-8 -*-
"""Advertencia no invasiva para flujo legado RET* (DEV)."""
from odoo import _, api, fields, models

LEGACY_RET_JOURNAL_CODES = frozenset({"RET01", "RET02"})


class AccountPaymentLegacyWithholding(models.Model):
    _inherit = "account.payment"

    justech_legacy_ret_journal = fields.Boolean(
        string="Diario legado de retención",
        compute="_compute_justech_legacy_ret_journal",
        help="True si el diario es RET01/RET02 (mecanismo legado).",
    )
    justech_legacy_ret_warning = fields.Char(
        string="Aviso legado retención",
        compute="_compute_justech_legacy_ret_journal",
    )

    # Contrato técnico Fase 1 (sin asientos nuevos) — campos documentales
    justech_wh_resolution_ready = fields.Boolean(
        string="Resolución WH v2 disponible",
        compute="_compute_justech_wh_contract_stub",
        help="Indica si el servicio _get_withholding_account está disponible (Fase 1).",
    )

    @api.depends("journal_id", "journal_id.code")
    def _compute_justech_legacy_ret_journal(self):
        msg = _(
            "Este pago utiliza el mecanismo legado de retenciones mediante diario. "
            "No debe utilizarse como modelo para nuevas operaciones."
        )
        for pay in self:
            code = (pay.journal_id.code or "").upper()
            is_legacy = code in LEGACY_RET_JOURNAL_CODES
            pay.justech_legacy_ret_journal = is_legacy
            pay.justech_legacy_ret_warning = msg if is_legacy else False

    def _compute_justech_wh_contract_stub(self):
        for pay in self:
            pay.justech_wh_resolution_ready = True

    def justech_get_withholding_account_for_catalog(self, catalog, date=None):
        """Contrato técnico: resolución fail-closed vía company.config (Fase 1+)."""
        self.ensure_one()
        return catalog._get_withholding_account(self.company_id, date=date or self.date)
