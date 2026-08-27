# -*- coding: utf-8 -*-
"""Force one account.payment for multi-invoice register when grouping is safe.

Odoo core defaults group_payment=False when >1 invoice is selected, which
creates N payments / N sequences / N receipts for a single bank transfer.
"""
from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _justech_is_physical_check_method(self):
        self.ensure_one()
        method = self.payment_method_line_id.payment_method_id
        code = (method.code or "") if method else ""
        name = (self.payment_method_line_id.name or "").lower()
        return code == "check_printing" or "cheque" in name or "check" in name

    @api.depends("can_edit_wizard", "payment_method_line_id")
    def _compute_group_payment(self):
        super()._compute_group_payment()
        for wizard in self:
            if not wizard.can_edit_wizard:
                continue
            # Partner wizard / Justech single-intent: keep one payment even for checks.
            if self.env.context.get("justech_force_group_payment"):
                if wizard.can_group_payments:
                    wizard.group_payment = True
                continue
            # Physical checks must remain one payment per instrument (native register).
            if wizard._justech_is_physical_check_method():
                wizard.group_payment = False
                continue
            if wizard.can_group_payments:
                wizard.group_payment = True
