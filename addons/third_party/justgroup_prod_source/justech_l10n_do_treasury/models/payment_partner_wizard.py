"""Tesorería: pagos abiertos sobre el wizard de pagos Justech."""
from __future__ import annotations

from odoo import fields, models
from odoo.exceptions import UserError


class JustechPaymentPartnerWizard(models.TransientModel):
    _inherit = "justech.payment.partner.wizard"

    treasury_operation_type = fields.Selection(
        [
            ("apply", "Aplicar a factura existente"),
            ("open", "Registrar pago abierto"),
        ],
        string="Tipo de operación",
        default="apply",
        required=True,
    )
    treasury_amount_received = fields.Monetary(
        string="Monto recibido",
        currency_field="currency_id",
    )
    TREASURY_OPEN_TYPES = ("open", "advance", "free")

    def _treasury_no_invoice_types(self):
        return self.TREASURY_OPEN_TYPES

    def _treasury_payment_type(self):
        self.ensure_one()
        return "inbound" if self.partner_type == "customer" else "outbound"

    def _treasury_advance_vals(self):
        self.ensure_one()
        common = self._register_vals_common()
        amount = self.treasury_amount_received
        if not amount or amount <= 0:
            raise UserError("El monto del pago debe ser mayor que cero.")
        return {
            "payment_type": self._treasury_payment_type(),
            "partner_type": self.partner_type,
            "partner_id": self.partner_id.id,
            "amount": amount,
            "currency_id": self.currency_id.id,
            "journal_id": self.journal_id.id,
            "payment_method_line_id": self.payment_method_line_id.id,
            "date": self.payment_date,
            "memo": self.communication or "Pago abierto",
            "justech_payment_reference": common.get("justech_payment_reference"),
            "justech_card_auth": common.get("justech_card_auth"),
            "justech_card_batch": common.get("justech_card_batch"),
            "justech_check_number": common.get("justech_check_number"),
            "justech_check_bank_id": common.get("justech_check_bank_id"),
            "justech_check_date": common.get("justech_check_date"),
        }

    def _treasury_register_open_payment(self):
        self.ensure_one()
        if not self.journal_id or not self.payment_method_line_id:
            raise UserError("Indique banco y método de pago.")
        if not self.partner_id:
            raise UserError("Indique el contacto.")
        payment = self.env["account.payment"].create(self._treasury_advance_vals())
        payment.action_post()
        return {
            "type": "ir.actions.act_window",
            "name": "Pago abierto registrado",
            "res_model": "account.payment",
            "res_id": payment.id,
            "view_mode": "form",
        }

    def action_register_payments(self):
        self.ensure_one()
        if self.treasury_operation_type in self._treasury_no_invoice_types():
            return self._treasury_register_open_payment()
        return super().action_register_payments()
