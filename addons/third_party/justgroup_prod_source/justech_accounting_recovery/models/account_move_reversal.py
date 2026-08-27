# -*- coding: utf-8 -*-
from odoo import models

from .accounting_recovery_guard import check_accounting_recovery


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self, is_modify=False):
        if self:
            check_accounting_recovery(self.env)
        return super().reverse_moves(is_modify=is_modify)
