# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    justech_applied_invoice_ids = fields.Many2many(
        "account.move",
        string="Documentos aplicados",
        compute="_compute_justech_applied_invoices",
        help="Facturas/bills conciliadas con este pago (una transferencia).",
    )
    justech_applied_invoice_html = fields.Html(
        string="Detalle aplicado",
        compute="_compute_justech_applied_invoices",
    )

    @api.depends(
        "move_id.line_ids.matched_debit_ids",
        "move_id.line_ids.matched_credit_ids",
        "state",
    )
    def _compute_justech_applied_invoices(self):
        for pay in self:
            moves = pay._justech_get_reconciled_invoices()
            pay.justech_applied_invoice_ids = moves
            rows = []
            total = 0.0
            for move in moves:
                amt = pay._justech_amount_applied_on_move(move)
                total += abs(amt)
                rows.append(
                    "<tr><td>%s</td><td class='text-end'>%s</td></tr>"
                    % (
                        move.display_name,
                        pay.currency_id.format(abs(amt)) if pay.currency_id else abs(amt),
                    )
                )
            if rows:
                pay.justech_applied_invoice_html = (
                    "<table class='table table-sm'>"
                    "<thead><tr><th>Documento</th><th class='text-end'>Aplicado</th></tr></thead>"
                    "<tbody>%s</tbody>"
                    "<tfoot><tr><th>TOTAL</th><th class='text-end'>%s</th></tr></tfoot>"
                    "</table>"
                    % (
                        "".join(rows),
                        pay.currency_id.format(total) if pay.currency_id else total,
                    )
                )
            else:
                pay.justech_applied_invoice_html = False

    def _justech_get_reconciled_invoices(self):
        self.ensure_one()
        if not self.move_id:
            return self.env["account.move"]
        amls = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        moves = self.env["account.move"]
        for aml in amls:
            for partial in aml.matched_debit_ids:
                other = partial.debit_move_id if partial.credit_move_id == aml else partial.credit_move_id
                if other.move_id and other.move_id.is_invoice(include_receipts=True):
                    moves |= other.move_id
            for partial in aml.matched_credit_ids:
                other = partial.credit_move_id if partial.debit_move_id == aml else partial.debit_move_id
                if other.move_id and other.move_id.is_invoice(include_receipts=True):
                    moves |= other.move_id
        return moves

    def _justech_amount_applied_on_move(self, move):
        """Monto aplicado en la moneda del pago (no company currency cruda)."""
        self.ensure_one()
        # Prefer Justech withholding helper when present (payment currency).
        helper = getattr(self, "_justech_applied_amount_for_invoice", None)
        if helper:
            return helper(move)
        amount = 0.0
        pay_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        inv_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        pay_currency = self.currency_id
        for aml in pay_lines:
            for partial in aml.matched_debit_ids | aml.matched_credit_ids:
                counterpart = (
                    partial.debit_move_id
                    if partial.credit_move_id == aml
                    else partial.credit_move_id
                )
                if counterpart not in inv_lines:
                    continue
                if partial.credit_move_id == counterpart:
                    curr_amt = abs(partial.credit_amount_currency or 0.0)
                else:
                    curr_amt = abs(partial.debit_amount_currency or 0.0)
                if curr_amt and (
                    counterpart.currency_id == pay_currency
                    or move.currency_id == pay_currency
                    or aml.currency_id == pay_currency
                ):
                    amount += curr_amt
                else:
                    amount += partial.amount or 0.0
        return amount
