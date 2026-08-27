# -*- coding: utf-8 -*-
from odoo import models, _

from odoo.addons.justech_vendor_bill_po_control.models.constants import (
    VENDOR_BILL_MOVE_TYPES,
)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        moves = self.line_ids.mapped("move_id")
        bills = moves.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES)
        if bills:
            bills._check_vendor_bill_approved_for_financial_processing(_("creación de pagos"))
        return super()._create_payments()


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_post(self):
        for pay in self:
            if pay.partner_type != "supplier":
                continue
            if not pay.company_id.vendor_bill_strict_approval:
                continue
            moves = self.env["account.move"]
            if "reconciled_invoice_ids" in pay._fields:
                moves |= pay.reconciled_invoice_ids
            if self.env.context.get("active_model") == "account.move" and self.env.context.get(
                "active_ids"
            ):
                moves |= self.env["account.move"].browse(self.env.context["active_ids"])
            bills = moves.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES)
            if bills:
                bills._check_vendor_bill_approved_for_financial_processing(_("confirmación de pago"))
        return super().action_post()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        pending = self.mapped("move_id").filtered(
            lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES
            and m.company_id.vendor_bill_strict_approval
            and m.vendor_bill_approval_state
            in ("pending_validation", "rejected", "returned", "draft")
            and m.vendor_bill_requires_approval
        )
        if pending:
            pending._check_vendor_bill_approved_for_financial_processing(_("conciliación"))
        return super().reconcile()
