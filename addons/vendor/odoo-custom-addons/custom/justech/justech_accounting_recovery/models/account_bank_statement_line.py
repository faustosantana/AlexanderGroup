# -*- coding: utf-8 -*-
"""Cascada legítima: undo de extracto → payment.unlink → button_draft."""
from odoo import models

from .accounting_recovery_guard import (
    payment_unlink_cascade_enter,
    payment_unlink_cascade_exit,
)


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_undo_reconciliation(self):
        """Único entry-point público que arma la excepción de cascada.

        No usa contexto ORM (no manipulable por RPC/with_context). Usa
        contador thread-local del módulo.
        """
        payment_unlink_cascade_enter()
        try:
            return super().action_undo_reconciliation()
        finally:
            payment_unlink_cascade_exit()
