# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.4 — bloquear pagos con monto <= 0 en todos los flujos."""
from odoo import api, models
from odoo.exceptions import UserError

JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG = "El monto del pago debe ser mayor que cero."


class AccountPaymentAmountGuard(models.Model):
    _inherit = "account.payment"

    def _justech_payment_amount_is_positive(self, amount, currency=None):
        """True si amount > 0 en la moneda dada (o company currency)."""
        self.ensure_one()
        currency = currency or self.currency_id or self.company_id.currency_id
        return currency.compare_amounts(amount or 0.0, 0.0) > 0

    def _justech_assert_payment_amount_positive(self):
        """Bloquea publicar / crear pagos con monto <= 0. No toca históricos ya publicados."""
        for pay in self:
            if not pay._justech_payment_amount_is_positive(pay.amount):
                raise UserError(JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    @api.model_create_multi
    def create(self, vals_list):
        """Bloquea amount <= 0 antes del INSERT (mensaje amigable vs check SQL)."""
        for vals in vals_list:
            amount = vals.get("amount", 0.0)
            currency = None
            if vals.get("currency_id"):
                currency = self.env["res.currency"].browse(vals["currency_id"])
            elif vals.get("company_id"):
                currency = self.env["res.company"].browse(vals["company_id"]).currency_id
            else:
                currency = self.env.company.currency_id
            if currency.compare_amounts(amount or 0.0, 0.0) <= 0:
                raise UserError(JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)
        return super().create(vals_list)

    def write(self, vals):
        """Impide bajar un monto positivo a <= 0.

        Los 7 pagos históricos con amount=0 pueden re-guardarse con el mismo
        monto (grandfather); no se corrigen ni cancelan aquí.
        """
        if "amount" in vals:
            new_amount = vals["amount"]
            for pay in self:
                currency = pay.currency_id or pay.company_id.currency_id
                becoming_non_positive = currency.compare_amounts(new_amount or 0.0, 0.0) <= 0
                was_positive = currency.compare_amounts(pay.amount or 0.0, 0.0) > 0
                if becoming_non_positive and was_positive:
                    raise UserError(JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)
                if becoming_non_positive and not was_positive:
                    if currency.compare_amounts(new_amount or 0.0, pay.amount or 0.0) != 0:
                        raise UserError(JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)
        return super().write(vals)

    def action_post(self):
        self._justech_assert_payment_amount_positive()
        res = super().action_post()
        # Detalle UX factura↔pago (no altera asientos ni conciliaciones).
        self._justech_sync_application_lines()
        return res
