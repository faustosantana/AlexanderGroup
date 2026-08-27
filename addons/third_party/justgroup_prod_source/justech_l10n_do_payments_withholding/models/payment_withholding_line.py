"""Retenciones persistentes — ciclo contable/fiscal completo."""
from __future__ import annotations

from odoo import api, fields, models


class JustechPaymentWithholdingLine(models.Model):
    _name = "justech.payment.withholding.line"
    _description = "Retención aplicada en pago"
    _order = "date desc, invoice_name, id"

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
        help="Factura a la que se aplica la retención.",
    )
    invoice_move_id = fields.Many2one(
        related="move_id",
        string="Asiento factura",
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente/Proveedor",
        related="payment_id.partner_id",
        store=True,
        index=True,
    )
    invoice_name = fields.Char(string="Factura", index=True)
    ncf = fields.Char(string="NCF", index=True)
    catalog_id = fields.Many2one("justech.do.withholding.catalog", string="Retención", index=True)
    withholding_code = fields.Char(related="catalog_id.code", string="Código retención", store=True)
    withholding_type = fields.Selection(related="catalog_id.withholding_type", store=True)
    label = fields.Char(string="Descripción", required=True)
    base_label = fields.Char(string="Tipo de base")
    base_amount = fields.Monetary(string="Base", currency_field="currency_id")
    rate = fields.Float(string="Porcentaje", digits=(16, 4))
    amount = fields.Monetary(string="Monto retenido", currency_field="currency_id", required=True)
    account_id = fields.Many2one("account.account", string="Cuenta contable", index=True)
    currency_id = fields.Many2one(related="payment_id.currency_id", store=True)
    company_id = fields.Many2one(related="payment_id.company_id", store=True, index=True)
    date = fields.Date(related="payment_id.date", store=True, index=True)
    affects_606 = fields.Boolean(related="catalog_id.affects_606", store=True)
    affects_607 = fields.Boolean(related="catalog_id.affects_607", store=True)
    affects_623 = fields.Boolean(related="catalog_id.affects_623", store=True)
    dgii_withholding_code = fields.Char(
        related="catalog_id.dgii_withholding_code",
        string="Código DGII",
        store=True,
    )
    fiscal_report_codes = fields.Char(
        compute="_compute_fiscal_report_codes",
        string="Reportes fiscales",
        store=True,
    )
    move_line_id = fields.Many2one(
        "account.move.line",
        string="Línea contable retención",
        ondelete="set null",
        index=True,
    )
    payment_move_id = fields.Many2one(
        related="payment_id.move_id",
        string="Asiento de pago",
        store=True,
    )
    partial_reconcile_id = fields.Many2one(
        "account.partial.reconcile",
        string="Conciliación parcial",
        ondelete="set null",
        index=True,
        help="Conciliación entre la línea CxC/CxP de la factura y el pago.",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("posted", "Contabilizado"),
        ],
        compute="_compute_state",
        store=True,
        string="Estado",
    )

    @api.depends(
        "catalog_id.affects_606",
        "catalog_id.affects_607",
        "catalog_id.affects_623",
        "catalog_id.code",
    )
    def _compute_fiscal_report_codes(self):
        gov_codes = ("RET-GOB-5", "wh_isr_gov", "RET5%")
        for line in self:
            codes = []
            if line.affects_606:
                codes.append("606")
            if line.affects_607:
                codes.append("607")
            if line.affects_623 or (line.catalog_id and line.catalog_id.code in gov_codes):
                if "623" not in codes:
                    codes.append("623")
            line.fiscal_report_codes = "/".join(codes)

    @api.depends("payment_id.state", "move_line_id")
    def _compute_state(self):
        for line in self:
            if line.payment_id.state == "posted" and line.move_line_id:
                line.state = "posted"
            elif line.payment_id.state == "posted":
                line.state = "posted"
            else:
                line.state = "draft"


class AccountPaymentWithholding(models.Model):
    _inherit = "account.payment"

    justech_applied_amount = fields.Monetary(
        string="Monto aplicado",
        currency_field="currency_id",
        copy=False,
        help="Importe bruto aplicado a la(s) factura(s) antes de retenciones.",
    )
    justech_withholding_line_ids = fields.One2many(
        "justech.payment.withholding.line",
        "payment_id",
        string="Retenciones aplicadas",
        copy=False,
    )
    justech_withholding_total = fields.Monetary(
        compute="_compute_justech_withholding_totals",
        string="Total retenido",
        currency_field="currency_id",
        store=True,
    )
    justech_net_transfer = fields.Monetary(
        compute="_compute_justech_withholding_totals",
        string="Neto transferido",
        currency_field="currency_id",
        store=True,
    )
    justech_invoice_display = fields.Char(
        compute="_compute_justech_invoice_display",
        string="Facturas afectadas",
    )
    justech_payment_reference = fields.Char(string="Referencia")
    justech_card_auth = fields.Char(string="Autorización")
    justech_card_batch = fields.Char(string="Lote")
    justech_check_number = fields.Char(string="Número de cheque")
    justech_check_bank_id = fields.Many2one("res.bank", string="Banco del cheque")
    justech_check_date = fields.Date(string="Fecha del cheque")
    justech_is_card = fields.Boolean(compute="_compute_justech_payment_flags")
    justech_is_check = fields.Boolean(compute="_compute_justech_payment_flags")
    justech_is_transfer = fields.Boolean(compute="_compute_justech_payment_flags")
    justech_is_cash = fields.Boolean(compute="_compute_justech_payment_flags")

    @api.depends("payment_method_line_id.name")
    def _compute_justech_payment_flags(self):
        for pay in self:
            name = (pay.payment_method_line_id.name or "").lower()
            pay.justech_is_card = "tarjeta" in name
            pay.justech_is_check = "cheque" in name
            pay.justech_is_transfer = "transferencia" in name
            pay.justech_is_cash = "efectivo" in name

    @api.depends(
        "justech_withholding_line_ids.amount",
        "justech_applied_amount",
        "amount",
        "state",
    )
    def _compute_justech_withholding_totals(self):
        for pay in self:
            wh_total = sum(pay.justech_withholding_line_ids.mapped("amount"))
            pay.justech_withholding_total = wh_total
            applied = pay.justech_applied_amount or pay.amount
            pay.justech_net_transfer = applied - wh_total

    def _justech_refresh_stored_totals(self):
        """Fuerza recálculo almacenado tras persistir líneas."""
        self.invalidate_recordset(["justech_withholding_line_ids"])
        self._compute_justech_withholding_totals()

    @api.depends(
        "justech_withholding_line_ids.invoice_name",
        "justech_withholding_line_ids.ncf",
        "reconciled_invoice_ids",
        "reconciled_bill_ids",
    )
    def _compute_justech_invoice_display(self):
        for pay in self:
            names = pay.justech_withholding_line_ids.mapped("invoice_name")
            if not names:
                moves = pay.reconciled_invoice_ids | pay.reconciled_bill_ids
                names = moves.mapped("name")
            pay.justech_invoice_display = ", ".join(filter(None, dict.fromkeys(names)))

    def _prepare_move_withholding_lines(self, default_values):
        """Líneas de retención en el asiento del pago — cuenta vía servicio único."""
        self.ensure_one()
        lines = []
        for wh in self.justech_withholding_line_ids.filtered(lambda w: w.amount):
            if wh.catalog_id:
                account = wh.catalog_id._get_withholding_account(
                    self.company_id, date=self.date
                )
            else:
                account = wh.account_id
            if not account:
                continue
            if wh.account_id != account:
                wh.account_id = account
            sign = -1 if self.payment_type == "outbound" else 1
            amount_currency = sign * wh.amount
            lines.append(
                {
                    "name": wh.label,
                    "account_id": account.id,
                    "partner_id": self.partner_id.id,
                    "currency_id": self.currency_id.id,
                    "amount_currency": amount_currency,
                    "balance": self.currency_id._convert(
                        amount_currency,
                        self.company_id.currency_id,
                        self.company_id,
                        self.date,
                    ),
                }
            )
        return lines

    def _justech_link_withholding_move_lines(self):
        for pay in self:
            if not pay.move_id:
                continue
            for wh in pay.justech_withholding_line_ids.filtered(lambda w: not w.move_line_id):
                candidates = pay.move_id.line_ids.filtered(
                    lambda l: l.account_id == wh.account_id
                    and abs(abs(l.balance) - wh.amount) < 0.02
                )
                if candidates:
                    wh.move_line_id = candidates[:1]

    def _justech_link_partial_reconciles(self):
        """Vincula cada línea persistente con la conciliación factura↔pago."""
        Partial = self.env["account.partial.reconcile"]
        valid_types = self._get_valid_payment_account_types()
        for pay in self:
            if not pay.move_id:
                continue
            pay_counterparts = pay.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in valid_types
            )
            for wh in pay.justech_withholding_line_ids.filtered(lambda w: w.move_id and not w.partial_reconcile_id):
                inv_lines = wh.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type in valid_types
                )
                for inv_line in inv_lines:
                    partials = Partial.search(
                        [
                            "|",
                            ("debit_move_id", "=", inv_line.id),
                            ("credit_move_id", "=", inv_line.id),
                        ]
                    )
                    for partial in partials:
                        other = (
                            partial.debit_move_id
                            if partial.credit_move_id == inv_line
                            else partial.credit_move_id
                        )
                        if other in pay_counterparts:
                            wh.partial_reconcile_id = partial.id
                            break
                    if wh.partial_reconcile_id:
                        break


class AccountMoveWithholding(models.Model):
    _inherit = "account.move"

    justech_withholding_line_ids = fields.One2many(
        "justech.payment.withholding.line",
        "move_id",
        string="Retenciones aplicadas",
        readonly=True,
    )
    justech_withholding_total = fields.Monetary(
        compute="_compute_justech_withholding_invoice",
        string="Total retenido",
        currency_field="currency_id",
    )

    @api.depends("justech_withholding_line_ids.amount")
    def _compute_justech_withholding_invoice(self):
        for move in self:
            move.justech_withholding_total = sum(move.justech_withholding_line_ids.mapped("amount"))
