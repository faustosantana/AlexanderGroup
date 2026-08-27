# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import AccessError

from .accounting_recovery_guard import (
    GROUP_ACCOUNTING_RECOVERY,
    accounting_recovery_denied_message,
    check_accounting_recovery,
    in_authorized_reversal,
    in_payment_unlink_cascade,
)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _justech_user_may_reverse_invoice(self):
        """Recuperación Contable O permiso Opción C «Revertir factura»."""
        user = self.env.user
        if user.has_group(GROUP_ACCOUNTING_RECOVERY):
            return True
        if user.has_group("justech_l10n_do_ncf.group_justech_reverse_invoice"):
            return True
        return False

    def _justech_check_reverse_permission(self):
        if in_authorized_reversal():
            return
        if self._justech_user_may_reverse_invoice():
            return
        raise AccessError(accounting_recovery_denied_message())

    def button_draft(self):
        # Solo recordsets no vacíos: Odoo llama estos métodos sobre []
        # en cascadas internas (p.ej. payment.action_post → _post_process).
        if self and not in_payment_unlink_cascade():
            check_accounting_recovery(self.env)
        return super().button_draft()

    def button_cancel(self):
        if self and not in_payment_unlink_cascade():
            check_accounting_recovery(self.env)
        return super().button_cancel()

    def button_request_cancel(self):
        if self:
            check_accounting_recovery(self.env)
        return super().button_request_cancel()

    def action_reverse(self):
        # Reversión de factura: Recovery O grupo «Revertir factura» (Opción C).
        if self and not in_payment_unlink_cascade():
            self._justech_check_reverse_permission()
        return super().action_reverse()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # Cascada payment.unlink → move.unlink → deferral _reverse_moves (EE)
        if self and not in_payment_unlink_cascade():
            self._justech_check_reverse_permission()
        return super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )

    def unlink(self):
        """Unlink de asientos / facturas: eliminación de información contable.

        Cascada legítima (payment.unlink autorizado o undo de extracto):
        no re-check. Unlink directo: exige Recuperación Contable.
        """
        if self and not in_payment_unlink_cascade():
            check_accounting_recovery(self.env)
        return super().unlink()
