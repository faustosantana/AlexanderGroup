"""H07 — cancelar/eliminar BORRADORES con permisos nativos de Facturación."""

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _dx_all_drafts(self):
        return bool(self) and all(move.state == "draft" for move in self)

    def _dx_skip_recovery_for_drafts(self):
        """Llama al super de Recuperación Contable (Odoo nativo) solo en borrador."""
        from odoo.addons.justech_accounting_recovery.models.account_move import (
            AccountMove as RecoveryMove,
        )

        return RecoveryMove

    def button_cancel(self):
        if self._dx_all_drafts():
            return super(self._dx_skip_recovery_for_drafts(), self).button_cancel()
        return super().button_cancel()

    def button_request_cancel(self):
        if self._dx_all_drafts():
            return super(
                self._dx_skip_recovery_for_drafts(), self
            ).button_request_cancel()
        return super().button_request_cancel()

    def unlink(self):
        if self._dx_all_drafts():
            return super(self._dx_skip_recovery_for_drafts(), self).unlink()
        return super().unlink()
