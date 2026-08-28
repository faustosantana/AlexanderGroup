# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class MultiInvoiceManualPaymentWizard(models.TransientModel):
    _name = "multi.invoice.manual.payment.wizard"
    _description = "Pagos de múltiples facturas"

    partner_type = fields.Selection(
        [("customer", "Cliente"), ("supplier", "Proveedor")],
        string="Tipo de Socio",
        required=True,
        default="customer",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente/Proveedor",
        required=True,
        check_company=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    payment_date = fields.Date(
        required=True, string="Fecha de Pago", default=fields.Date.context_today
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit')), ('company_id', '=', company_id)]",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Método de pago",
        domain="[('journal_id', '=', journal_id)]",
    )

    ref = fields.Char(string="Referencia / Memo")
    payment_receipt = fields.Binary(string="Comprobante de pago")
    payment_receipt_filename = fields.Char(string="Nombre del comprobante")

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Moneda",
        store=False,
    )
    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda del pago",
        compute="_compute_payment_currency_id",
        store=False,
    )
    amount_received = fields.Monetary(
        string="Monto de la transferencia",
        currency_field="payment_currency_id",
        help="Monto físico de la transferencia / depósito.",
    )
    amount_total_to_apply = fields.Monetary(
        string="Total aplicado",
        currency_field="payment_currency_id",
        compute="_compute_amount_total_to_apply",
        store=False,
    )
    amount_difference = fields.Monetary(
        string="Diferencia",
        currency_field="payment_currency_id",
        compute="_compute_amount_total_to_apply",
        store=False,
    )
    duplicate_warning = fields.Char(compute="_compute_duplicate_warning")
    check_warning = fields.Char(compute="_compute_check_warning")
    line_ids = fields.One2many(
        "multi.invoice.manual.payment.wizard.line",
        "wizard_id",
        string="Facturas",
    )
    line_count = fields.Integer(compute="_compute_line_count", store=False)

    @api.depends("journal_id", "company_id")
    def _compute_payment_currency_id(self):
        for wizard in self:
            wizard.payment_currency_id = (
                wizard.journal_id.currency_id or wizard.company_id.currency_id
            )

    def _convert_amount(self, amount, from_currency, to_currency, date):
        self.ensure_one()
        if not amount or not from_currency or not to_currency:
            return 0.0
        if from_currency == to_currency:
            return amount
        return from_currency._convert(
            amount,
            to_currency,
            self.company_id,
            date or fields.Date.context_today(self),
        )

    @api.depends(
        "line_ids.amount_to_apply",
        "line_ids.currency_id",
        "payment_currency_id",
        "payment_date",
        "amount_received",
    )
    def _compute_amount_total_to_apply(self):
        for wizard in self:
            total = 0.0
            for line in wizard.line_ids.filtered(lambda l: l.move_id and l.amount_to_apply):
                total += wizard._convert_amount(
                    line.amount_to_apply,
                    line.currency_id,
                    wizard.payment_currency_id,
                    wizard.payment_date,
                )
            wizard.amount_total_to_apply = total
            received = wizard.amount_received or 0.0
            wizard.amount_difference = received - total if received else 0.0

    @api.depends("line_ids")
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.depends(
        "partner_id",
        "journal_id",
        "payment_date",
        "amount_received",
        "amount_total_to_apply",
        "ref",
        "company_id",
    )
    def _compute_duplicate_warning(self):
        Payment = self.env["account.payment"]
        for wizard in self:
            wizard.duplicate_warning = False
            amount = wizard.amount_received or wizard.amount_total_to_apply
            if not (
                wizard.partner_id
                and wizard.journal_id
                and wizard.payment_date
                and amount
            ):
                continue
            domain = [
                ("partner_id", "=", wizard.partner_id.commercial_partner_id.id),
                ("journal_id", "=", wizard.journal_id.id),
                ("date", "=", wizard.payment_date),
                ("amount", "=", amount),
                ("company_id", "=", wizard.company_id.id),
                ("state", "!=", "canceled"),
            ]
            if wizard.ref:
                domain += [
                    "|",
                    ("memo", "=", wizard.ref),
                    ("payment_reference", "=", wizard.ref),
                ]
            twins = Payment.search(domain, limit=3)
            if twins:
                wizard.duplicate_warning = _(
                    "Ya existe un pago con esta referencia/monto/fecha: %s"
                ) % ", ".join(twins.mapped("name"))

    @api.depends("payment_method_line_id", "line_ids.amount_to_apply")
    def _compute_check_warning(self):
        for wizard in self:
            wizard.check_warning = False
            method = wizard.payment_method_line_id.payment_method_id
            code = (method.code or "") if method else ""
            name = (wizard.payment_method_line_id.name or "").lower()
            is_check = code == "check_printing" or "cheque" in name or "check" in name
            applied = wizard.line_ids.filtered(lambda l: l.amount_to_apply > 0)
            if is_check and len(applied) > 1:
                wizard.check_warning = _(
                    "Método cheque: una transferencia/cheque físico debe "
                    "corresponder a un solo instrumento. Confirme que es "
                    "correcto aplicar un único cheque a %s documentos."
                ) % len(applied)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if self.company_id:
            self.journal_id = False
            self.payment_method_line_id = False
            self.line_ids = [(5, 0, 0)]

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        if self.journal_id:
            method = (
                self.journal_id.inbound_payment_method_line_ids[:1]
                if self.partner_type == "customer"
                else self.journal_id.outbound_payment_method_line_ids[:1]
            )
            self.payment_method_line_id = method.id if method else False

    @api.onchange("partner_type")
    def _onchange_partner_type(self):
        self.line_ids = [(5, 0, 0)]
        if self.journal_id:
            self._onchange_journal_id()

    def _get_open_moves_domain(self):
        self.ensure_one()
        if not self.partner_id or not self.company_id:
            return [("id", "=", 0)]

        commercial_partner = self.partner_id.commercial_partner_id
        move_types = (
            ["out_invoice", "out_refund"]
            if self.partner_type == "customer"
            else ["in_invoice", "in_refund"]
        )

        return [
            ("company_id", "=", self.company_id.id),
            ("commercial_partner_id", "=", commercial_partner.id),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("move_type", "in", move_types),
            ("amount_residual", ">", 0),
        ]

    def _load_open_moves(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        invoices = self.env["account.move"].search(
            self._get_open_moves_domain(),
            order="currency_id asc, invoice_date_due asc, invoice_date asc, id asc",
        )
        self.line_ids = [
            (
                0,
                0,
                {
                    "move_id": inv.id,
                    "currency_id": inv.currency_id.id,
                    "invoice_date": inv.invoice_date,
                    "due_date": inv.invoice_date_due,
                    "amount_total": abs(inv.amount_total),
                    "amount_residual": abs(inv.amount_residual),
                    "amount_to_apply": 0.0,
                },
            )
            for inv in invoices
        ]

    @api.onchange("partner_id", "partner_type", "company_id")
    def _onchange_partner_id(self):
        for wizard in self:
            wizard._load_open_moves()

    def action_load_open_moves(self):
        self.ensure_one()
        self._load_open_moves()
        return self._reopen_self()

    def action_fill_full_balance(self):
        for line in self.line_ids:
            line.amount_to_apply = line.amount_residual
        return self._reopen_self()

    def action_clear_amounts(self):
        for line in self.line_ids:
            line.amount_to_apply = 0.0
        return self._reopen_self()

    def _reopen_self(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pago de múltiples facturas"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _cleanup_empty_lines(self):
        self.ensure_one()
        empty_lines = self.line_ids.filtered(lambda l: not l.move_id)
        if empty_lines:
            empty_lines.unlink()

    def _validate_before_post(self):
        self.ensure_one()
        self._cleanup_empty_lines()

        if not self.line_ids:
            raise ValidationError(
                _(
                    "No se cargaron facturas pendientes. Verifique la empresa, el socio y que los documentos estén registrados con un saldo pendiente mayor que cero."
                )
            )
        if not self.journal_id:
            raise ValidationError(_("Por favor, seleccione un banco o un libro de caja."))
        if not self.payment_method_line_id:
            raise ValidationError(_("Por favor, seleccione un método de pago."))
        if not self.payment_currency_id:
            raise ValidationError(
                _("La moneda del pago no pudo ser determinada desde el diario seleccionado.")
            )

        valid_lines = self.line_ids.filtered(lambda l: l.move_id and l.amount_to_apply > 0)
        if not valid_lines:
            raise ValidationError(_("Debe introducir una cantidad mayor que cero."))

        currencies = valid_lines.mapped("currency_id")
        if len(currencies) > 1 and any(
            c != self.payment_currency_id for c in currencies
        ):
            # Conversion is supported, but silent mix of incompatible company rules
            # is blocked when journal has no FX path — require explicit payment currency.
            pass

        for line in valid_lines:
            if line.move_id.state != "posted":
                raise ValidationError(
                    _("Factura %s no está publicada") % line.move_id.display_name
                )
            if line.move_id.payment_state == "paid":
                raise ValidationError(
                    _("Factura %s está completamente pagada") % line.move_id.display_name
                )
            if line.move_id.company_id != self.company_id:
                raise ValidationError(
                    _(
                        "Factura %s pertenece a otra empresa. Solo puede pagar documentos de la empresa seleccionada."
                    )
                    % line.move_id.display_name
                )
            if line.move_id.commercial_partner_id != self.partner_id.commercial_partner_id:
                raise ValidationError(
                    _(
                        "No se pueden agrupar documentos de partners distintos (%s)."
                    )
                    % line.move_id.display_name
                )
            if float_compare(
                line.amount_to_apply,
                line.amount_residual,
                precision_rounding=line.currency_id.rounding,
            ) > 0:
                raise ValidationError(
                    _(
                        "El importe a aplicar sobre %s no puede ser mayor que el importe residual."
                    )
                    % line.move_id.display_name
                )

        if self.amount_received and float_compare(
            self.amount_total_to_apply,
            self.amount_received,
            precision_rounding=self.payment_currency_id.rounding,
        ) > 0:
            raise ValidationError(
                _(
                    "El total aplicado (%s) supera el monto de la transferencia (%s)."
                )
                % (self.amount_total_to_apply, self.amount_received)
            )

        return valid_lines

    def _get_open_invoice_lines(self, move, account):
        receivable_payable_types = ("asset_receivable", "liability_payable")
        return move.line_ids.filtered(
            lambda l: (
                l.account_id == account
                and l.account_id.account_type in receivable_payable_types
                and not l.reconciled
            )
        ).sorted(
            key=lambda l: (abs(l.amount_residual_currency or l.amount_residual), l.id),
            reverse=True,
        )

    def _amount_for_line_currency(
        self, amount_company, target_currency, source_amount, source_currency
    ):
        self.ensure_one()
        if not target_currency:
            return 0.0
        if target_currency == self.company_currency_id:
            return abs(amount_company)
        if source_currency and target_currency == source_currency:
            return abs(source_amount)
        return abs(
            self.company_currency_id._convert(
                amount_company,
                target_currency,
                self.company_id,
                self.payment_date or fields.Date.context_today(self),
            )
        )

    def _prepare_partial_reconcile_vals(
        self, debit_line, credit_line, amount_invoice_currency, invoice_currency
    ):
        self.ensure_one()
        amount_company = self._convert_amount(
            amount_invoice_currency,
            invoice_currency,
            self.company_currency_id,
            self.payment_date,
        )
        vals = {
            "debit_move_id": debit_line.id,
            "credit_move_id": credit_line.id,
            "amount": abs(self.company_currency_id.round(amount_company)),
        }
        if debit_line.currency_id:
            vals["debit_amount_currency"] = self._amount_for_line_currency(
                amount_company, debit_line.currency_id, amount_invoice_currency, invoice_currency
            )
        if credit_line.currency_id:
            vals["credit_amount_currency"] = self._amount_for_line_currency(
                amount_company, credit_line.currency_id, amount_invoice_currency, invoice_currency
            )
        return vals

    def action_create_payment(self):
        self.ensure_one()
        valid_lines = self._validate_before_post()

        total_amount_payment_currency = 0.0
        for line in valid_lines:
            total_amount_payment_currency += self._convert_amount(
                line.amount_to_apply,
                line.currency_id,
                self.payment_currency_id,
                self.payment_date,
            )

        if self.amount_received and not float_is_zero(
            self.amount_received, precision_rounding=self.payment_currency_id.rounding
        ):
            # Header amount is source of truth when provided (allows open credit).
            payment_amount = self.amount_received
        else:
            payment_amount = total_amount_payment_currency

        if float_is_zero(
            payment_amount, precision_rounding=self.payment_currency_id.rounding
        ):
            raise UserError(_("El monto total a pagar debe ser mayor que cero."))

        payment_type = "inbound" if self.partner_type == "customer" else "outbound"
        payment_vals = {
            "payment_type": payment_type,
            "partner_type": self.partner_type,
            "partner_id": self.partner_id.id,
            "amount": payment_amount,
            "date": self.payment_date,
            "journal_id": self.journal_id.id,
            "payment_method_line_id": self.payment_method_line_id.id,
            "currency_id": self.payment_currency_id.id,
            "company_id": self.company_id.id,
            "memo": self.ref or False,
            "payment_reference": self.ref or False,
        }
        Payment = self.env["account.payment"]
        if "memo" not in Payment._fields:
            payment_vals.pop("memo", None)
        if "payment_reference" not in Payment._fields:
            payment_vals.pop("payment_reference", None)

        payment = Payment.create(payment_vals)

        if self.payment_receipt:
            self.env["ir.attachment"].sudo().create(
                {
                    "name": self.payment_receipt_filename or "Comprobante de pago",
                    "type": "binary",
                    "datas": self.payment_receipt,
                    "res_model": "account.payment",
                    "res_id": payment.id,
                }
            )

        payment.action_post()

        receivable_payable_types = ("asset_receivable", "liability_payable")
        payment_open_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in receivable_payable_types
            and not l.reconciled
        )
        if not payment_open_lines:
            raise UserError(
                _(
                    "No se encontró ninguna línea de cuentas por cobrar/pagar pendientes en el registro de pago."
                )
            )

        payment_line = payment_open_lines[0]

        for wizard_line in valid_lines:
            amount_left_for_invoice = wizard_line.amount_to_apply
            invoice_lines = self._get_open_invoice_lines(
                wizard_line.move_id, payment_line.account_id
            )

            if not invoice_lines:
                raise UserError(
                    _(
                        "No se encontró ninguna línea de cuentas por cobrar/pagar abierta en %s usando la cuenta %s."
                    )
                    % (
                        wizard_line.move_id.display_name,
                        payment_line.account_id.display_name,
                    )
                )

            for invoice_line in invoice_lines:
                invoice_residual = abs(
                    invoice_line.amount_residual_currency or invoice_line.amount_residual
                )
                amount_to_reconcile = min(amount_left_for_invoice, invoice_residual)

                if float_is_zero(
                    amount_to_reconcile,
                    precision_rounding=wizard_line.currency_id.rounding,
                ):
                    continue

                if payment_line.balance > 0:
                    debit_line = payment_line
                    credit_line = invoice_line
                else:
                    debit_line = invoice_line
                    credit_line = payment_line

                vals = self._prepare_partial_reconcile_vals(
                    debit_line,
                    credit_line,
                    amount_to_reconcile,
                    wizard_line.currency_id,
                )
                self.env["account.partial.reconcile"].create(vals)

                payment_line.invalidate_recordset()
                invoice_line.invalidate_recordset()

                amount_left_for_invoice -= amount_to_reconcile

                if float_is_zero(
                    amount_left_for_invoice,
                    precision_rounding=wizard_line.currency_id.rounding,
                ):
                    break

            if not float_is_zero(
                amount_left_for_invoice,
                precision_rounding=wizard_line.currency_id.rounding,
            ):
                raise UserError(
                    _(
                        "El sistema no pudo conciliar el importe total solicitado para %s. Saldo pendiente de conciliación: %s"
                    )
                    % (wizard_line.move_id.display_name, amount_left_for_invoice)
                )

        return {
            "type": "ir.actions.act_window",
            "name": _("Pago"),
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": payment.id,
            "target": "current",
        }


class MultiInvoiceManualPaymentWizardLine(models.TransientModel):
    _name = "multi.invoice.manual.payment.wizard.line"
    _description = "Pago de múltiples facturas"
    _order = "currency_id asc, due_date asc, invoice_date asc, id asc"

    wizard_id = fields.Many2one(
        "multi.invoice.manual.payment.wizard",
        required=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one("account.move", string="Factura")
    document_number = fields.Char(
        string="Número de documento",
        compute="_compute_document_number",
        store=False,
    )

    company_id = fields.Many2one(related="wizard_id.company_id", store=False)
    currency_id = fields.Many2one("res.currency", string="Moneda", required=True)
    invoice_date = fields.Date(string="Fecha")
    due_date = fields.Date(string="Vencimiento")
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    amount_residual = fields.Monetary(string="Saldo", currency_field="currency_id")
    amount_to_apply = fields.Monetary(
        string="Aplicar", currency_field="currency_id"
    )
    payment_currency_id = fields.Many2one(
        related="wizard_id.payment_currency_id",
        string="Moneda de pago",
        store=False,
    )
    amount_to_apply_payment_currency = fields.Monetary(
        string="Monto en moneda de pago",
        currency_field="payment_currency_id",
        compute="_compute_amount_to_apply_payment_currency",
        store=False,
    )

    @api.depends("move_id")
    def _compute_document_number(self):
        for line in self:
            move = line.move_id
            if move and "l10n_latam_document_number" in move._fields:
                line.document_number = move.l10n_latam_document_number or move.name or ""
            elif move:
                line.document_number = move.name or move.ref or ""
            else:
                line.document_number = ""

    @api.depends(
        "amount_to_apply",
        "currency_id",
        "wizard_id.payment_currency_id",
        "wizard_id.payment_date",
    )
    def _compute_amount_to_apply_payment_currency(self):
        for line in self:
            wizard = line.wizard_id
            if (
                not wizard
                or not wizard.payment_currency_id
                or not line.currency_id
                or not line.amount_to_apply
            ):
                line.amount_to_apply_payment_currency = 0.0
                continue
            if line.currency_id == wizard.payment_currency_id:
                line.amount_to_apply_payment_currency = line.amount_to_apply
            else:
                line.amount_to_apply_payment_currency = line.currency_id._convert(
                    line.amount_to_apply,
                    wizard.payment_currency_id,
                    wizard.company_id,
                    wizard.payment_date or fields.Date.context_today(line),
                )

    @api.constrains("amount_to_apply", "amount_residual")
    def _check_amount_to_apply(self):
        for line in self:
            if not line.move_id:
                continue
            if line.amount_to_apply < 0:
                raise ValidationError(_("El monto a aplicar no puede ser negativo."))
            if line.currency_id and float_compare(
                line.amount_to_apply,
                line.amount_residual,
                precision_rounding=line.currency_id.rounding,
            ) > 0:
                raise ValidationError(
                    _("El monto a aplicar no puede ser mayor que el monto residual.")
                )
