"""Líneas persistentes de aplicación pago ↔ factura (detalle UX)."""
from __future__ import annotations

from odoo import api, fields, models


class JustechPaymentApplicationLine(models.Model):
    _name = "justech.payment.application.line"
    _description = "Aplicación de pago por factura"
    _order = "invoice_date, invoice_name, id"

    payment_id = fields.Many2one(
        "account.payment",
        string="Pago",
        required=True,
        ondelete="cascade",
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        index=True,
        ondelete="set null",
    )
    invoice_name = fields.Char(string="Factura", index=True)
    ncf = fields.Char(
        string="NCF / e-CF",
        index=True,
        help="Comprobante fiscal (NCF o e-CF) de la factura.",
    )
    invoice_date = fields.Date(string="Fecha")
    invoice_total = fields.Monetary(
        string="Total factura",
        currency_field="currency_id",
        help="Total de la factura (snapshot de display).",
    )
    applied_amount = fields.Monetary(
        string="Monto aplicado",
        currency_field="currency_id",
        help="Monto aplicado por este pago a la factura (vía conciliación).",
    )
    withholding_labels = fields.Char(string="Retenciones")
    withholding_amount = fields.Monetary(string="Monto retenido", currency_field="currency_id")
    net_amount = fields.Monetary(string="Neto", currency_field="currency_id")
    reconciliation_state = fields.Char(string="Estado de conciliación")
    currency_id = fields.Many2one(
        related="payment_id.currency_id",
        string="Moneda",
        store=True,
    )
    company_id = fields.Many2one(related="payment_id.company_id", store=True, index=True)

    # --- Display-only related (no write-back to accounting) ---
    partner_id = fields.Many2one(
        related="move_id.partner_id",
        string="Cliente / Proveedor",
        store=False,
    )
    move_currency_id = fields.Many2one(
        related="move_id.currency_id",
        string="Moneda de factura",
        store=False,
    )
    # Fuente de verdad: residual contable vivo de account.move (otros pagos, NC, etc.).
    amount_residual = fields.Monetary(
        related="move_id.amount_residual",
        string="Balance pendiente",
        currency_field="move_currency_id",
        store=False,
        help=(
            "Saldo pendiente actual de la factura (account.move.amount_residual). "
            "Respeta otros pagos, notas de crédito y conciliaciones; no es total − este pago."
        ),
    )
    payment_state = fields.Selection(
        related="move_id.payment_state",
        string="Estado de pago",
        store=False,
    )
    # Conservado en modelo por compatibilidad; NO se muestra en esta UX de pago.
    justech_do_fiscal_ui_status = fields.Selection(
        related="move_id.justech_do_fiscal_ui_status",
        string="Estado fiscal",
        store=False,
    )

    def action_justech_open_invoice(self):
        """Abrir el formulario completo de la factura (account.move)."""
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.move_id.display_name,
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_justech_open_partner(self):
        """Abrir la ficha del cliente/proveedor."""
        self.ensure_one()
        partner = self.partner_id or self.move_id.partner_id
        if not partner:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": partner.display_name,
            "res_model": "res.partner",
            "res_id": partner.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_justech_open_payment(self):
        """Abrir el pago relacionado."""
        self.ensure_one()
        if not self.payment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.payment_id.display_name,
            "res_model": "account.payment",
            "res_id": self.payment_id.id,
            "view_mode": "form",
            "target": "current",
        }


class AccountPaymentApplication(models.Model):
    _inherit = "account.payment"

    justech_application_line_ids = fields.One2many(
        "justech.payment.application.line",
        "payment_id",
        string="Detalle por factura",
        copy=False,
    )
    justech_show_application_detail = fields.Boolean(
        compute="_compute_justech_show_application_detail",
    )
    justech_related_invoice_count = fields.Integer(
        compute="_compute_justech_related_invoice_count",
        string="Facturas",
    )

    @api.depends(
        "justech_application_line_ids",
        "justech_applied_amount",
        "justech_withholding_total",
        "reconciled_invoice_ids",
        "reconciled_bill_ids",
        "state",
    )
    def _compute_justech_show_application_detail(self):
        for pay in self:
            pay.justech_show_application_detail = bool(
                pay.justech_application_line_ids
                or pay.justech_applied_amount
                or pay.justech_withholding_total
                or pay.reconciled_invoice_ids
                or pay.reconciled_bill_ids
                or pay.state == "posted"
            )

    @api.depends(
        "reconciled_invoice_ids",
        "reconciled_bill_ids",
        "justech_application_line_ids.move_id",
        "justech_withholding_line_ids.move_id",
    )
    def _compute_justech_related_invoice_count(self):
        for pay in self:
            moves = pay.reconciled_invoice_ids | pay.reconciled_bill_ids
            moves |= pay.justech_application_line_ids.mapped("move_id")
            moves |= pay.justech_withholding_line_ids.mapped("move_id")
            pay.justech_related_invoice_count = len(moves)

    def action_justech_view_related_invoices(self):
        self.ensure_one()
        self._justech_ensure_application_lines()
        moves = self.reconciled_invoice_ids | self.reconciled_bill_ids
        moves |= self.justech_application_line_ids.mapped("move_id")
        moves |= self.justech_withholding_line_ids.mapped("move_id")
        moves = moves.exists()
        if not moves:
            return False
        action = {
            "type": "ir.actions.act_window",
            "name": "Facturas relacionadas",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }
        if len(moves) == 1:
            action.update({"view_mode": "form", "res_id": moves.id})
        return action

    def action_justech_view_payment_move(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Asiento contable",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_justech_refresh_related_invoices(self):
        """Recalcular detalle UX de facturas (no altera conciliación ni asientos)."""
        self._justech_sync_application_lines()
        return True

    def _justech_ensure_application_lines(self):
        """Si hay facturas conciliadas y falta detalle UX, sincronizar líneas de display."""
        to_sync = self.filtered(
            lambda p: p.state in ("posted", "in_process", "paid")
            and (p.reconciled_invoice_ids or p.reconciled_bill_ids or p.move_id)
            and not p.justech_application_line_ids
        )
        if to_sync:
            to_sync._justech_sync_application_lines()

    def _justech_applied_amount_for_invoice(self, move):
        """Monto aplicado a una factura en la moneda del pago."""
        self.ensure_one()
        if not self.move_id or not move:
            return 0.0
        valid_types = self._get_valid_payment_account_types()
        pay_lines = self.move_id.line_ids.filtered(lambda l: l.account_id.account_type in valid_types)
        inv_lines = move.line_ids.filtered(lambda l: l.account_id.account_type in valid_types)
        applied = 0.0
        pay_currency = self.currency_id
        for inv_line in inv_lines:
            for partial in inv_line.matched_debit_ids | inv_line.matched_credit_ids:
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id == inv_line
                    else partial.credit_move_id
                )
                if other not in pay_lines:
                    continue
                # Prefer currency amount matching the payment currency.
                if partial.credit_move_id == inv_line:
                    curr_amt = abs(partial.credit_amount_currency or 0.0)
                else:
                    curr_amt = abs(partial.debit_amount_currency or 0.0)
                if curr_amt and (
                    inv_line.currency_id == pay_currency
                    or other.currency_id == pay_currency
                    or move.currency_id == pay_currency
                ):
                    applied += curr_amt
                else:
                    # Fallback: company amount → payment currency.
                    company_amt = partial.amount or 0.0
                    if pay_currency == self.company_id.currency_id:
                        applied += company_amt
                    else:
                        applied += self.company_id.currency_id._convert(
                            company_amt,
                            pay_currency,
                            self.company_id,
                            self.date or fields.Date.context_today(self),
                        )
        if applied:
            return applied
        moves = self.reconciled_invoice_ids | self.reconciled_bill_ids
        if move in moves and len(moves) == 1 and self.justech_applied_amount:
            return self.justech_applied_amount
        if move in moves and len(moves) == 1:
            return self.amount
        return 0.0

    def _justech_reconciliation_label(self, move):
        labels = {
            "not_paid": "Sin pagar",
            "in_payment": "En proceso de pago",
            "partial": "Parcialmente pagada",
            "paid": "Pagada",
            "reversed": "Revertida",
        }
        return labels.get(move.payment_state, move.payment_state or "")

    def _justech_invoices_from_payment(self):
        """Facturas vinculadas al pago vía campos Odoo o conciliaciones."""
        self.ensure_one()
        moves = self.reconciled_invoice_ids | self.reconciled_bill_ids
        if moves:
            return moves
        moves = self.justech_withholding_line_ids.mapped("move_id")
        if moves:
            return moves
        if not self.move_id:
            return self.env["account.move"]
        valid_types = self._get_valid_payment_account_types()
        pay_lines = self.move_id.line_ids.filtered(lambda l: l.account_id.account_type in valid_types)
        found = self.env["account.move"]
        invoice_types = ("out_invoice", "out_refund", "in_invoice", "in_refund")
        for pay_line in pay_lines:
            for partial in pay_line.matched_debit_ids | pay_line.matched_credit_ids:
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id == pay_line
                    else partial.credit_move_id
                )
                if other.move_id.move_type in invoice_types:
                    found |= other.move_id
        return found

    def _justech_sync_application_lines(self):
        """Sincroniza líneas de detalle UX. No modifica asientos ni conciliaciones."""
        AppLine = self.env["justech.payment.application.line"]
        Provider = self.env["justech.do.fiscal.data.provider"]
        for pay in self.filtered(lambda p: p.state in ("posted", "in_process", "paid")):
            moves = pay._justech_invoices_from_payment()
            moves.mapped("line_ids.matched_debit_ids")
            moves.mapped("line_ids.matched_credit_ids")
            if pay.move_id:
                pay.move_id.line_ids.mapped("matched_debit_ids")
                pay.move_id.line_ids.mapped("matched_credit_ids")
            pay.justech_application_line_ids.unlink()
            if not moves:
                continue
            vals_list = []
            for move in moves:
                wh_lines = pay.justech_withholding_line_ids.filtered(lambda w: w.move_id == move)
                wh_amount = sum(wh_lines.mapped("amount"))
                applied = pay._justech_applied_amount_for_invoice(move)
                if not applied and pay.justech_applied_amount and len(moves) == 1:
                    applied = pay.justech_applied_amount
                if not applied:
                    applied = pay.amount
                vals_list.append(
                    {
                        "payment_id": pay.id,
                        "move_id": move.id,
                        "invoice_name": move.name,
                        "ncf": Provider.get_ncf(move) or "",
                        "invoice_date": move.invoice_date,
                        "invoice_total": move.amount_total,
                        "applied_amount": applied,
                        "withholding_labels": ", ".join(filter(None, wh_lines.mapped("label"))),
                        "withholding_amount": wh_amount,
                        "net_amount": applied - wh_amount,
                        "reconciliation_state": pay._justech_reconciliation_label(move),
                    }
                )
            if vals_list:
                AppLine.create(vals_list)
