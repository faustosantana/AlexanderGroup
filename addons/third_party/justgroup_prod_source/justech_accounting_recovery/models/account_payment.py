# -*- coding: utf-8 -*-
from odoo import models

from .accounting_recovery_guard import (
    check_accounting_recovery,
    in_payment_unlink_cascade,
    payment_unlink_cascade_enter,
    payment_unlink_cascade_exit,
)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_draft(self):
        if self:
            check_accounting_recovery(self.env)
        return super().action_draft()

    def action_cancel(self):
        # account_payment.action_post llama action_cancel sobre [] cuando
        # no hay transacciones pendientes — no es recuperación iniciada
        # por el usuario.
        if self:
            check_accounting_recovery(self.env)
        return super().action_cancel()

    def button_request_cancel(self):
        if self:
            check_accounting_recovery(self.env)
        return super().button_request_cancel()

    def unlink(self):
        """Unlink con SoD (cualquier estado, incluido draft).

        Cascada legítima (flag thread-local ya activo): no re-check.
        Unlink directo: exige Recuperación Contable; luego arma el flag
        para anidados (move.unlink / button_draft / _reverse_moves).
        """
        if in_payment_unlink_cascade():
            return super().unlink()

        if self:
            check_accounting_recovery(self.env)

        payment_unlink_cascade_enter()
        try:
            return super().unlink()
        finally:
            payment_unlink_cascade_exit()
