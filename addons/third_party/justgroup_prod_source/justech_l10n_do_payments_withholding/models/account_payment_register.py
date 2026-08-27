"""Extensión account.payment.register — montos parciales y datos de pago Justech."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .account_payment_amount import JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG


class AccountPaymentRegisterJustech(models.TransientModel):
    _inherit = "account.payment.register"

    justech_payment_reference = fields.Char(string="Referencia")
    justech_card_auth = fields.Char(string="Autorización")
    justech_card_batch = fields.Char(string="Lote")
    justech_check_number = fields.Char(string="Número de cheque")
    justech_check_bank_id = fields.Many2one("res.bank", string="Banco del cheque")
    justech_check_date = fields.Date(string="Fecha del cheque")
    justech_show_card_fields = fields.Boolean(compute="_compute_justech_method_flags")
    justech_show_check_fields = fields.Boolean(compute="_compute_justech_method_flags")

    @api.depends("payment_method_line_id.name")
    def _compute_justech_method_flags(self):
        for wiz in self:
            name = (wiz.payment_method_line_id.name or "").lower()
            wiz.justech_show_card_fields = "tarjeta" in name
            wiz.justech_show_check_fields = "cheque" in name

    @api.depends("can_edit_wizard", "payment_method_line_id")
    def _compute_group_payment(self):
        """Una intención Justech (partner wizard) → un solo account.payment.

        Context justech_force_group_payment: el usuario confirmó un único cobro/pago
        sobre N facturas compatibles; no partir en N secuencias.
        """
        super()._compute_group_payment()
        if not self.env.context.get("justech_force_group_payment"):
            return
        for wizard in self:
            if wizard.can_group_payments:
                wizard.group_payment = True

    def _justech_extra_payment_vals(self):
        self.ensure_one()
        vals = {
            "justech_payment_reference": self.justech_payment_reference,
            "justech_card_auth": self.justech_card_auth,
            "justech_card_batch": self.justech_card_batch,
            "justech_check_number": self.justech_check_number,
            "justech_check_bank_id": self.justech_check_bank_id.id,
            "justech_check_date": self.justech_check_date,
        }
        if self.justech_payment_reference:
            vals["memo"] = self.justech_payment_reference
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            forced = vals.get("custom_user_amount") or self.env.context.get("justech_applied_amount")
            if forced is not None:
                vals["amount"] = forced
                vals["custom_user_amount"] = forced
                if not vals.get("custom_user_currency_id"):
                    vals["custom_user_currency_id"] = vals.get("currency_id")
                vals.setdefault("payment_difference_handling", "open")
            prepared.append(vals)
        registers = super().create(prepared)
        for register, vals in zip(registers, prepared):
            forced = vals.get("custom_user_amount")
            if forced is None:
                continue
            if register.currency_id.compare_amounts(register.amount, forced) != 0:
                register.write(
                    {
                        "amount": forced,
                        "custom_user_amount": forced,
                        "custom_user_currency_id": register.currency_id.id,
                        "payment_difference_handling": "open",
                    }
                )
        return registers

    def _justech_assert_register_amount_positive(self):
        """Bloquea account.payment.register / lotes con monto <= 0."""
        for wiz in self:
            currency = wiz.currency_id or wiz.company_id.currency_id
            amount = wiz.custom_user_amount if wiz.custom_user_amount else wiz.amount
            if currency.compare_amounts(amount or 0.0, 0.0) <= 0:
                raise UserError(JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def _create_payments(self):
        self._justech_assert_register_amount_positive()
        if self.env.context.get("justech_force_group_payment"):
            for wiz in self:
                if wiz.can_group_payments and not wiz.group_payment:
                    wiz.group_payment = True
        return super()._create_payments()

    def _create_payment_vals_from_wizard(self, batch_result):
        self._justech_assert_register_amount_positive()
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals.update(self._justech_extra_payment_vals())
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        self._justech_assert_register_amount_positive()
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals.update(self._justech_extra_payment_vals())
        return vals
