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

    def _is_user_able_to_review(self):
        """Anular / restablecer no debe exigir el grupo de revisor."""
        if self.env.context.get("dx_posted_lifecycle"):
            return True
        return super()._is_user_able_to_review()

    def button_draft(self):
        """Restablecer a borrador. No exige Recuperación Contable ni revisor."""
        if self:
            return super(
                self._dx_skip_recovery_for_drafts(),
                self.with_context(dx_posted_lifecycle=True),
            ).button_draft()
        return super().button_draft()

    def button_cancel(self):
        if not self._dx_all_drafts():
            self._dx_void_ncf_before_cancel()
            # Native cancel drafts first; checked entries block non-reviewers.
            return super(
                self._dx_skip_recovery_for_drafts(),
                self.with_context(dx_posted_lifecycle=True),
            ).button_cancel()
        return super(self._dx_skip_recovery_for_drafts(), self).button_cancel()

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
