# -*- coding: utf-8 -*-
import html as html_lib

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
        "amount",
        "currency_id",
    )
    def _compute_justech_applied_invoices(self):
        for pay in self:
            moves = pay._justech_get_reconciled_invoices()
            pay.justech_applied_invoice_ids = moves
            pay.justech_applied_invoice_html = (
                pay._justech_render_receipt_html() if moves else False
            )

    def _justech_partner_vat(self, partner):
        if not partner:
            return ""
        for fname in ("justech_do_rnc", "vat"):
            if fname in partner._fields and partner[fname]:
                return partner[fname]
        return ""

    def _justech_move_ncf(self, move):
        for fname in ("justech_do_ncf", "l10n_latam_document_number"):
            if fname in move._fields and move[fname]:
                return move[fname]
        return move.name or move.ref or ""

    def _justech_receipt_payload(self):
        """Structured receipt data for QWeb / HTML (one payment → N invoices)."""
        self.ensure_one()
        rows = []
        total_applied = 0.0
        for move in self._justech_get_reconciled_invoices():
            applied = abs(self._justech_amount_applied_on_move(move))
            residual_after = abs(move.amount_residual)
            residual_before = residual_after + applied
            rows.append(
                {
                    "move": move,
                    "name": move.name or "",
                    "ncf": self._justech_move_ncf(move),
                    "invoice_date": move.invoice_date,
                    "due_date": move.invoice_date_due,
                    "amount_total": abs(move.amount_total),
                    "balance_before": residual_before,
                    "applied": applied,
                    "balance_after": residual_after,
                }
            )
            total_applied += applied
        amount = self.amount or 0.0
        unapplied = amount - total_applied if amount > total_applied else 0.0
        method = ""
        if self.payment_method_line_id:
            method = self.payment_method_line_id.name or ""
        if not method and self.payment_method_id:
            method = self.payment_method_id.name or ""
        reference = self.memo or self.payment_reference or ""
        company_partner = self.company_id.partner_id if self.company_id else False
        return {
            "is_vendor": self.partner_type == "supplier",
            "company_name": self.company_id.name if self.company_id else "",
            "company_vat": self._justech_partner_vat(company_partner),
            "partner_name": self.partner_id.display_name if self.partner_id else "",
            "partner_vat": self._justech_partner_vat(self.partner_id),
            "receipt_number": self.name or "",
            "payment_date": self.date,
            "currency": self.currency_id.name if self.currency_id else "",
            "method": method,
            "journal": self.journal_id.display_name if self.journal_id else "",
            "reference": reference,
            "observations": reference,
            "amount_received": amount,
            "total_applied": total_applied,
            "unapplied": unapplied,
            "rows": rows,
        }

    def _justech_fmt_money(self, amount):
        if self.currency_id:
            return self.currency_id.format(amount)
        return "%.2f" % (amount or 0.0)

    def _justech_fmt_date(self, value):
        return value.strftime("%Y-%m-%d") if value else ""

    def _justech_render_receipt_html(self):
        self.ensure_one()
        data = self._justech_receipt_payload()
        invoice_label = "FACTURA PROVEEDOR" if data["is_vendor"] else "FACTURA"
        rows_html = []
        for row in data["rows"]:
            rows_html.append(
                "<tr>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td>%s</td>"
                "<td class='text-end'>%s</td>"
                "<td class='text-end'>%s</td>"
                "<td class='text-end'>%s</td>"
                "<td class='text-end'>%s</td>"
                "</tr>"
                % (
                    html_lib.escape(row["name"]),
                    html_lib.escape(row["ncf"]),
                    html_lib.escape(self._justech_fmt_date(row["invoice_date"])),
                    html_lib.escape(self._justech_fmt_date(row["due_date"])),
                    html_lib.escape(self._justech_fmt_money(row["amount_total"])),
                    html_lib.escape(self._justech_fmt_money(row["balance_before"])),
                    html_lib.escape(self._justech_fmt_money(row["applied"])),
                    html_lib.escape(self._justech_fmt_money(row["balance_after"])),
                )
            )
        table = (
            "<table class='table table-sm table-bordered justech-receipt-applied'>"
            "<thead><tr>"
            "<th>%s</th><th>NCF</th><th>FECHA FACTURA</th>"
            "<th>FECHA VENCIMIENTO</th><th class='text-end'>MONTO ORIGINAL</th>"
            "<th class='text-end'>SALDO ANTES</th>"
            "<th class='text-end'>MONTO APLICADO</th>"
            "<th class='text-end'>SALDO RESULTANTE</th>"
            "</tr></thead><tbody>%s</tbody></table>"
            % (invoice_label, "".join(rows_html))
        )
        footer = (
            "<table class='table table-sm justech-receipt-footer'>"
            "<tr><th>TOTAL RECIBIDO</th><td class='text-end'>%s</td></tr>"
            "<tr><th>TOTAL APLICADO</th><td class='text-end'>%s</td></tr>"
            "<tr><th>SALDO NO APLICADO</th><td class='text-end'>%s</td></tr>"
            "<tr><th>FORMA DE PAGO</th><td>%s</td></tr>"
            "<tr><th>REFERENCIA</th><td>%s</td></tr>"
            "<tr><th>OBSERVACIONES</th><td>%s</td></tr>"
            "</table>"
            % (
                html_lib.escape(self._justech_fmt_money(data["amount_received"])),
                html_lib.escape(self._justech_fmt_money(data["total_applied"])),
                html_lib.escape(self._justech_fmt_money(data["unapplied"])),
                html_lib.escape(data["method"]),
                html_lib.escape(data["reference"]),
                html_lib.escape(data["observations"]),
            )
        )
        return table + footer

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
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id == aml
                    else partial.credit_move_id
                )
                if other.move_id and other.move_id.is_invoice(include_receipts=True):
                    moves |= other.move_id
            for partial in aml.matched_credit_ids:
                other = (
                    partial.credit_move_id
                    if partial.debit_move_id == aml
                    else partial.debit_move_id
                )
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
