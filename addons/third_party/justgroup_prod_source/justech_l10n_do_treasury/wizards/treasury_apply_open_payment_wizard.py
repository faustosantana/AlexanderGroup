"""Wizard definitivo para aplicar pagos abiertos a facturas (solo conciliación Odoo estándar)."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class TreasuryOpenPaymentApplyWizardLine(models.TransientModel):
    _name = "treasury.open.payment.apply.wizard.line"
    _description = "Línea aplicación pago abierto"

    wizard_id = fields.Many2one(
        "treasury.open.payment.apply.wizard",
        required=True,
        ondelete="cascade",
    )
    apply = fields.Boolean(string="Aplicar", default=True)
    payment_id = fields.Many2one(
        "account.payment",
        string="Pago",
        required=True,
        readonly=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="wizard_id.currency_id",
        readonly=True,
    )
    invoice_name = fields.Char(string="Factura", readonly=True)
    ncf = fields.Char(string="NCF", readonly=True)
    invoice_date = fields.Date(string="Fecha", readonly=True)
    date_maturity = fields.Date(string="Vencimiento", readonly=True)
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        readonly=True,
    )
    invoice_residual = fields.Monetary(
        string="Pendiente",
        currency_field="currency_id",
        readonly=True,
    )
    withholding_amount = fields.Monetary(
        string="Retención",
        currency_field="currency_id",
        readonly=True,
    )
    payment_available = fields.Monetary(
        string="Saldo pago",
        currency_field="currency_id",
        readonly=True,
    )
    amount = fields.Monetary(
        string="Monto a aplicar",
        currency_field="currency_id",
    )
    balance_after_apply = fields.Monetary(
        string="Saldo luego de aplicar",
        currency_field="currency_id",
        compute="_compute_balance_after_apply",
        readonly=True,
    )
    line_state = fields.Char(
        string="Estado",
        compute="_compute_balance_after_apply",
        readonly=True,
    )

    @api.depends("amount", "invoice_residual", "apply")
    def _compute_balance_after_apply(self):
        for line in self:
            if not line.apply:
                line.balance_after_apply = line.invoice_residual
                line.line_state = ""
                continue
            residual = max(line.invoice_residual - (line.amount or 0.0), 0.0)
            line.balance_after_apply = residual
            if float_is_zero(residual, precision_rounding=line.currency_id.rounding):
                line.line_state = "Pagada"
            elif line.amount:
                line.line_state = "Parcial"
            else:
                line.line_state = "Pendiente"

    @api.onchange("apply", "amount")
    def _onchange_apply_amount(self):
        for line in self:
            if not line.apply:
                line.amount = 0.0


class TreasuryOpenPaymentApplyWizard(models.TransientModel):
    _name = "treasury.open.payment.apply.wizard"
    _description = "Aplicar pagos abiertos"

    partner_id = fields.Many2one("res.partner", required=True, readonly=True)
    partner_type = fields.Selection(
        [("customer", "Cliente"), ("supplier", "Proveedor")],
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Factura objetivo",
        readonly=True,
    )
    payment_id = fields.Many2one(
        "account.payment",
        string="Pago abierto",
        readonly=True,
    )
    line_ids = fields.One2many(
        "treasury.open.payment.apply.wizard.line",
        "wizard_id",
        string="Aplicaciones",
    )

    # ------------------------------------------------------------------ helpers
    @api.model
    def _move_types_for_partner(self, partner_type):
        return ("out_invoice",) if partner_type == "customer" else ("in_invoice",)

    @api.model
    def _invoice_withholding_amount(self, move):
        wh_lines = getattr(move, "justech_withholding_line_ids", self.env["justech.payment.withholding.line"])
        return sum(wh_lines.filtered(lambda w: w.move_id == move).mapped("amount"))

    @api.model
    def _suggested_apply_amount(self, payment, move):
        """Monto efectivo en efectivo a aplicar desde el pago abierto."""
        pay_cur = payment.currency_id
        inv_cur = move.currency_id
        available = payment.treasury_amount_available
        residual = abs(move.amount_residual)
        if pay_cur != inv_cur:
            available = pay_cur._convert(
                available, inv_cur, move.company_id, move.invoice_date or fields.Date.context_today(self)
            )
        return min(available, residual)

    @api.model
    def _prepare_line_vals(self, payment, move):
        inv_cur = move.currency_id
        return {
            "apply": True,
            "payment_id": payment.id,
            "move_id": move.id,
            "invoice_name": move.name,
            "ncf": self.env["justech.do.fiscal.data.provider"].get_ncf(move) or "",
            "invoice_date": move.invoice_date,
            "date_maturity": move.invoice_date_due,
            "amount_total": move.amount_total,
            "invoice_residual": abs(move.amount_residual),
            "withholding_amount": self._invoice_withholding_amount(move),
            "payment_available": payment.treasury_amount_available,
            "amount": self._suggested_apply_amount(payment, move),
        }

    @api.model
    def _build_lines(self, partner, partner_type, payment=None, move=None):
        Payment = self.env["account.payment"]
        Move = self.env["account.move"]
        open_payments = Payment._treasury_search_open_for_partner(partner, partner_type)
        pending_moves = Move.search(
            [
                ("partner_id", "=", partner.id),
                ("move_type", "in", self._move_types_for_partner(partner_type)),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
            ],
            order="invoice_date, id",
        )
        lines = []
        if move and open_payments:
            for pay in open_payments:
                if payment and pay != payment:
                    continue
                lines.append(self._prepare_line_vals(pay, move))
        elif payment and pending_moves:
            for inv in pending_moves:
                if move and inv != move:
                    continue
                lines.append(self._prepare_line_vals(payment, inv))
        elif payment and move:
            lines.append(self._prepare_line_vals(payment, move))
        return lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner = self.env["res.partner"].browse(res.get("partner_id"))
        partner_type = res.get("partner_type")
        if not partner or not partner_type:
            return res

        payment = self.env["account.payment"].browse(res["payment_id"]) if res.get("payment_id") else False
        move = self.env["account.move"].browse(res["move_id"]) if res.get("move_id") else False
        lines = self._build_lines(partner, partner_type, payment=payment, move=move)
        if lines:
            res["line_ids"] = [(0, 0, vals) for vals in lines]
            if move:
                res["currency_id"] = move.currency_id.id
            elif payment:
                res["currency_id"] = payment.currency_id.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Garantiza líneas al crear el wizard desde la UI (evita payment_id vacío)."""
        records = super().create(vals_list)
        for wizard in records:
            if wizard.line_ids:
                continue
            lines = wizard._build_lines(
                wizard.partner_id,
                wizard.partner_type,
                payment=wizard.payment_id,
                move=wizard.move_id,
            )
            if lines:
                wizard.write({"line_ids": [(0, 0, vals) for vals in lines]})
        return records

    # ------------------------------------------------------------------ validation
    def _validate_line(self, line):
        payment = line.payment_id
        move = line.move_id
        rounding = line.currency_id.rounding

        if not payment or not move:
            raise UserError(_("Falta el pago o la factura en la línea de aplicación."))

        if payment.state == "canceled" or move.state == "cancel":
            raise UserError(_("No puede aplicar pagos o facturas anulados."))

        if move.state != "posted":
            raise UserError(_("Solo puede aplicar pagos a facturas confirmadas."))

        if payment.partner_id != self.partner_id or move.partner_id != self.partner_id:
            raise UserError(_("El pago y la factura deben pertenecer al mismo contacto."))

        if not payment.treasury_is_open and float_is_zero(
            payment.treasury_amount_available, precision_rounding=rounding
        ):
            raise UserError(
                _("El pago %(name)s no tiene saldo disponible.", name=payment.display_name)
            )

        if payment.currency_id != move.currency_id:
            raise UserError(
                _(
                    "El pago %(pay)s y la factura %(inv)s deben estar en la misma moneda "
                    "(%(pay_cur)s vs %(inv_cur)s).",
                    pay=payment.display_name,
                    inv=move.name,
                    pay_cur=payment.currency_id.name,
                    inv_cur=move.currency_id.name,
                )
            )

        available = payment.treasury_amount_available
        residual = abs(move.amount_residual)
        if float_compare(line.amount, available, precision_rounding=rounding) > 0:
            raise UserError(
                _(
                    "El monto a aplicar (%(amount).2f) supera el saldo disponible del pago "
                    "(%(available).2f).",
                    amount=line.amount,
                    available=available,
                )
            )
        if float_compare(line.amount, residual, precision_rounding=rounding) > 0:
            raise UserError(
                _(
                    "El monto a aplicar (%(amount).2f) supera el pendiente de la factura "
                    "(%(residual).2f).",
                    amount=line.amount,
                    residual=residual,
                )
            )

    def _reconcile_amount(self, payment, move, amount):
        """Concilia montos usando account.move.line (Odoo estándar)."""
        valid_types = payment._get_valid_payment_account_types()
        pay_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in valid_types and line.amount_residual
        )
        inv_lines = move.line_ids.filtered(
            lambda line: line.account_id.account_type in valid_types and line.amount_residual
        )
        if not pay_lines or not inv_lines:
            raise UserError(
                _(
                    "No hay líneas contables conciliables entre el pago %(pay)s y la factura %(inv)s.",
                    pay=payment.display_name,
                    inv=move.name,
                )
            )

        pay_line = pay_lines[0]
        inv_line = inv_lines[0]
        rounding = payment.currency_id.rounding
        max_apply = min(abs(pay_line.amount_residual), abs(inv_line.amount_residual))

        if float_is_zero(amount, precision_rounding=rounding):
            return

        if float_compare(amount, max_apply, precision_rounding=rounding) > 0:
            raise UserError(
                _(
                    "El monto a aplicar (%(amount).2f) supera lo conciliable ahora (%(max).2f).",
                    amount=amount,
                    max=max_apply,
                )
            )

        # Odoo concilia el mínimo entre ambas líneas; el monto debe coincidir con ese mínimo.
        if float_compare(amount, max_apply, precision_rounding=rounding) != 0:
            raise UserError(
                _(
                    "Para esta factura debe aplicar exactamente %(max).2f. "
                    "Ajuste el monto o aplique el saldo restante a otra factura.",
                    max=max_apply,
                )
            )

        (pay_line + inv_line).reconcile()

    @api.model
    def _validate_amount_positive(self, amount):
        if float_is_zero(amount, precision_rounding=0.01):
            raise UserError(_("Indique un monto a aplicar mayor que cero."))

    def action_apply(self):
        self.ensure_one()
        selected = self.line_ids.filtered(lambda line: line.apply and not float_is_zero(line.amount or 0.0, precision_rounding=line.currency_id.rounding))
        if not selected:
            raise UserError(_("Seleccione al menos una aplicación con monto mayor que cero."))

        # Orden: pagos con menor saldo primero si hay varias líneas del mismo pago
        for line in selected.sorted(key=lambda l: (l.payment_id.id, l.move_id.id)):
            self._validate_line(line)
            self._reconcile_amount(line.payment_id, line.move_id, line.amount)
            line.payment_id.invalidate_recordset(
                [
                    "treasury_amount_available",
                    "treasury_amount_applied",
                    "treasury_open_state",
                    "treasury_is_open",
                ]
            )
            line.move_id.invalidate_recordset(["amount_residual", "payment_state"])
            if hasattr(line.payment_id, "_justech_sync_application_lines"):
                line.payment_id._justech_sync_application_lines()

        return {"type": "ir.actions.act_window_close"}
