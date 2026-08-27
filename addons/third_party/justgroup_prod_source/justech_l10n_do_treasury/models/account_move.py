"""Alerta de pagos abiertos al crear facturas (solo UX, sin alterar contabilidad)."""
from __future__ import annotations

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    treasury_has_open_payments = fields.Boolean(
        compute="_compute_treasury_open_payment_alert",
    )
    treasury_open_payment_count = fields.Integer(
        string="Pagos abiertos",
        compute="_compute_treasury_open_payment_alert",
    )
    treasury_open_payment_balance = fields.Monetary(
        string="Saldo pagos abiertos",
        currency_field="currency_id",
        compute="_compute_treasury_open_payment_alert",
    )
    treasury_open_payment_message = fields.Char(
        compute="_compute_treasury_open_payment_alert",
    )

    def _treasury_partner_type_for_move(self):
        self.ensure_one()
        if self.move_type in ("out_invoice", "out_refund"):
            return "customer"
        if self.move_type in ("in_invoice", "in_refund"):
            return "supplier"
        return False

    @api.depends("partner_id", "move_type", "state", "currency_id")
    def _compute_treasury_open_payment_alert(self):
        Payment = self.env["account.payment"]
        for move in self:
            partner_type = move._treasury_partner_type_for_move()
            if (
                move.state != "draft"
                or not move.partner_id
                or not partner_type
                or move.move_type not in ("out_invoice", "in_invoice")
            ):
                move.treasury_has_open_payments = False
                move.treasury_open_payment_count = 0
                move.treasury_open_payment_balance = 0.0
                move.treasury_open_payment_message = ""
                continue

            open_payments = Payment._treasury_search_open_for_partner(
                move.partner_id, partner_type
            )
            balance = sum(open_payments.mapped("treasury_amount_available"))
            move.treasury_has_open_payments = bool(open_payments)
            move.treasury_open_payment_count = len(open_payments)
            move.treasury_open_payment_balance = balance
            if open_payments:
                symbol = move.currency_id.symbol or move.company_id.currency_id.symbol
                move.treasury_open_payment_message = (
                    f"Este contacto tiene pagos abiertos disponibles. "
                    f"Saldo disponible: {symbol} {balance:,.2f}"
                )
            else:
                move.treasury_open_payment_message = ""

    def action_treasury_apply_open_payments(self):
        self.ensure_one()
        partner_type = self._treasury_partner_type_for_move()
        return {
            "type": "ir.actions.act_window",
            "name": "Aplicar pagos abiertos",
            "res_model": "treasury.open.payment.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_partner_type": partner_type,
            },
        }

    def action_treasury_view_open_payments(self):
        self.ensure_one()
        partner_type = self._treasury_partner_type_for_move()
        action_xml = (
            "justech_l10n_do_treasury.action_treasury_open_payments_customer"
            if partner_type == "customer"
            else "justech_l10n_do_treasury.action_treasury_open_payments_vendor"
        )
        action = self.env.ref(action_xml).read()[0]
        action["domain"] = [
            ("partner_id", "=", self.partner_id.id),
            ("treasury_is_open", "=", True),
        ]
        return action
