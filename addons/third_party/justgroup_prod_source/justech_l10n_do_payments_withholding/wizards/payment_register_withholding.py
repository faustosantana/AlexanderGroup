"""Retenciones RD por factura en account.payment.register — Fase 2 (servicio único)."""
from __future__ import annotations

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


LEGACY_RET_JOURNAL_CODES = frozenset({"RET01", "RET02"})


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    justech_withholding_catalog_ids = fields.Many2many(
        "justech.do.withholding.catalog",
        "justech_payment_register_wh_catalog_rel",
        "register_id",
        "catalog_id",
        string="Retenciones",
        help="Solo retenciones activas, configuradas y vigentes para la empresa.",
    )
    justech_selectable_withholding_ids = fields.Many2many(
        "justech.do.withholding.catalog",
        compute="_compute_justech_selectable_withholding_ids",
        string="Retenciones seleccionables",
    )
    justech_withholding_line_ids = fields.One2many(
        "justech.payment.withholding.wizard.line",
        "register_wizard_id",
        string="Retenciones de la factura",
    )
    justech_withholding_total = fields.Monetary(
        compute="_compute_justech_withholding_total",
        string="Total retenido",
        currency_field="currency_id",
    )

    @api.depends("justech_withholding_line_ids.amount")
    def _compute_justech_withholding_total(self):
        for wiz in self:
            wiz.justech_withholding_total = sum(wiz.justech_withholding_line_ids.mapped("amount"))

    def _justech_partner_type(self):
        self.ensure_one()
        if self.payment_type == "inbound":
            return "customer"
        if self.payment_type == "outbound":
            return "supplier"
        return "customer"

    def _justech_move_scope(self, move):
        if move.move_type in ("out_invoice", "out_refund"):
            return "sale"
        return "purchase"

    def _justech_invoice_for_batch(self, batch_result):
        move = self.env["account.move"]
        if batch_result and batch_result.get("lines"):
            move = batch_result["lines"].move_id[:1]
        if not move and self.line_ids:
            move = self.line_ids.move_id[:1]
        return move

    @api.depends(
        "company_id",
        "payment_date",
        "payment_type",
        "line_ids",
        "justech_withholding_catalog_ids",
    )
    def _compute_justech_selectable_withholding_ids(self):
        Catalog = self.env["justech.do.withholding.catalog"]
        for wiz in self:
            move = wiz._justech_invoice_for_batch({})
            company = (move.company_id if move else wiz.company_id) or wiz.env.company
            if not company:
                wiz.justech_selectable_withholding_ids = Catalog.browse()
                continue
            wiz.justech_selectable_withholding_ids = Catalog._search_payment_selectable(
                company=company,
                partner_type=wiz._justech_partner_type(),
                move_scope=wiz._justech_move_scope(move) if move else None,
                date=wiz.payment_date,
            )

    def _justech_rebuild_register_withholding_lines(self):
        for wiz in self:
            move = wiz._justech_invoice_for_batch({})
            if not move:
                wiz.justech_withholding_line_ids = [Command.clear()]
                continue
            partner_type = wiz._justech_partner_type()
            company = move.company_id or wiz.company_id
            applied = wiz.custom_user_amount or wiz.amount or abs(move.amount_residual)
            details = [Command.clear()]
            for catalog in wiz.justech_withholding_catalog_ids:
                account, amount, info = catalog.with_context(
                    justech_payment_withholding=True
                ).resolve_for_payment(
                    company=company,
                    move=move,
                    partner_type=partner_type,
                    applied_amount=applied,
                    date=wiz.payment_date,
                )
                if not amount:
                    raise UserError(
                        f"La retención «{catalog.display_name}» resolvió monto cero "
                        f"para {move.name}."
                    )
                tax = catalog.get_tax_for_company(company) or catalog.tax_id
                details.append(
                    Command.create(
                        {
                            "catalog_id": catalog.id,
                            "company_id": company.id,
                            "catalog_code": info.get("catalog_code") or catalog.code,
                            "tax_id": tax.id if tax else False,
                            "label": catalog.name,
                            "base_label": catalog._base_label(),
                            "base_amount": catalog._base_amount(move, applied_amount=applied),
                            "rate": catalog.rate,
                            "amount": amount,
                            "account_id": account.id,
                            "account_code": info.get("account_code"),
                            "account_nature": info.get("account_nature"),
                            "config_state": info.get("state"),
                            "date_from": info.get("date_from"),
                            "date_to": info.get("date_to"),
                            "currency_id": wiz.currency_id.id,
                        }
                    )
                )
            wiz.justech_withholding_line_ids = details

    @api.onchange("justech_withholding_catalog_ids", "amount", "payment_date")
    def _onchange_justech_withholding_catalogs(self):
        self._justech_rebuild_register_withholding_lines()

    def _justech_assert_no_legacy_ret_journal(self):
        for wiz in self:
            if not wiz.justech_withholding_catalog_ids and not wiz.justech_withholding_line_ids:
                continue
            code = (wiz.journal_id.code or "").upper()
            if code in LEGACY_RET_JOURNAL_CODES:
                raise UserError(
                    "No puede combinar retenciones del catálogo Justech con diarios "
                    "legado RET01/RET02. Use un diario de banco/caja operativo."
                )

    def _justech_validate_withholdings_before_create(self):
        self._justech_assert_no_legacy_ret_journal()
        for wiz in self:
            if not wiz.justech_withholding_catalog_ids:
                continue
            wiz._justech_rebuild_register_withholding_lines()
            for wh in wiz.justech_withholding_line_ids:
                if not wh.catalog_id or not wh.account_id:
                    raise UserError("Retención sin cuenta contable válida — pago bloqueado.")
                move = wiz._justech_invoice_for_batch({})
                company = (move.company_id if move else wiz.company_id) or wiz.env.company
                resolved = wh.catalog_id._get_withholding_account(company, date=wiz.payment_date)
                if resolved != wh.account_id:
                    raise UserError(
                        f"Inconsistencia de cuenta en {wh.label}: "
                        f"esperada {resolved.display_name}."
                    )

    def _justech_persistent_vals(self, wh, default_move):
        move = default_move
        if getattr(wh, "wizard_line_id", False) and wh.wizard_line_id.move_id:
            move = wh.wizard_line_id.move_id
        ncf = ""
        if move:
            ncf = self.env["justech.do.fiscal.data.provider"].get_ncf(move) or ""
        return {
            "move_id": move.id if move else False,
            "invoice_name": move.name if move else "",
            "ncf": ncf,
            "catalog_id": wh.catalog_id.id,
            "label": wh.label or (wh.catalog_id.name if wh.catalog_id else wh.tax_id.name),
            "base_label": wh.base_label,
            "base_amount": wh.base_amount,
            "rate": wh.rate,
            "amount": wh.amount,
            "account_id": wh.account_id.id,
        }

    def _justech_persistent_withholding_commands(self, batch_result):
        fallback_move = self._justech_invoice_for_batch(batch_result)
        commands = []
        for wh in self.justech_withholding_line_ids:
            if not wh.amount or not wh.account_id:
                continue
            move = fallback_move
            # Partner wizard: cada retención pertenece a una factura concreta.
            if getattr(wh, "wizard_line_id", False) and wh.wizard_line_id.move_id:
                move = wh.wizard_line_id.move_id
            commands.append(Command.create(self._justech_persistent_vals(wh, move)))
        return commands
    def _justech_apply_withholding_to_payment_vals(self, payment_vals, batch_result):
        """Retenciones vía hook nativo _prepare_move_withholding_lines."""
        applied = self.custom_user_amount or self.amount or payment_vals.get("amount") or 0.0
        if applied:
            payment_vals["justech_applied_amount"] = applied

        wh_lines = self.justech_withholding_line_ids.filtered("amount")
        wh_total = sum(wh_lines.mapped("amount"))
        if not wh_total:
            return payment_vals

        payment_vals["justech_withholding_line_ids"] = self._justech_persistent_withholding_commands(
            batch_result
        )
        # payment.amount = bruto; banco = neto vía hook nativo.
        if wh_total:
            payment_vals["write_off_line_vals"] = []
        return payment_vals

    def _create_payment_vals_from_wizard(self, batch_result):
        self._justech_validate_withholdings_before_create()
        if self.justech_withholding_catalog_ids:
            self._justech_rebuild_register_withholding_lines()
        vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._justech_apply_withholding_to_payment_vals(vals, batch_result)

    def _create_payment_vals_from_batch(self, batch_result):
        self._justech_validate_withholdings_before_create()
        vals = super()._create_payment_vals_from_batch(batch_result)
        return self._justech_apply_withholding_to_payment_vals(vals, batch_result)

    def _justech_ensure_move_withholding_lines(self, payment):
        """Re-sincroniza asiento si las líneas persistentes no generaron GL."""
        payment.ensure_one()
        if payment.state != "draft" or not payment.justech_withholding_line_ids:
            return
        wh_accounts = payment.justech_withholding_line_ids.mapped("account_id")
        gl_wh = payment.move_id.line_ids.filtered(lambda l: l.account_id in wh_accounts)
        if not gl_wh:
            payment._synchronize_to_moves(set())

    def _justech_finalize_persistent_lines(self, payment, batch_result):
        """Persistencia, vínculos contables y stamp fiscal post-create."""
        move = self._justech_invoice_for_batch(batch_result)
        WhLine = self.env["justech.payment.withholding.line"]
        AppLine = self.env["justech.payment.application.line"]
        for pay in payment:
            if not pay.justech_withholding_line_ids:
                for wh in self.justech_withholding_line_ids:
                    if not wh.amount or not wh.account_id:
                        continue
                    WhLine.create({"payment_id": pay.id, **self._justech_persistent_vals(wh, move)})
            self._justech_ensure_move_withholding_lines(pay)
            pay._justech_refresh_stored_totals()
            if move and not pay.justech_application_line_ids:
                wh_lines = pay.justech_withholding_line_ids.filtered(lambda w: w.move_id == move)
                wh_amount = sum(wh_lines.mapped("amount"))
                applied = pay.justech_applied_amount or self.custom_user_amount or self.amount or pay.amount
                AppLine.create(
                    {
                        "payment_id": pay.id,
                        "move_id": move.id,
                        "invoice_name": move.name,
                        "ncf": self.env["justech.do.fiscal.data.provider"].get_ncf(move) or "",
                        "invoice_date": move.invoice_date,
                        "invoice_total": move.amount_total,
                        "applied_amount": applied,
                        "withholding_labels": ", ".join(filter(None, wh_lines.mapped("label"))),
                        "withholding_amount": wh_amount,
                        "net_amount": applied - wh_amount,
                        "reconciliation_state": "Pendiente",
                    }
                )
            pay._justech_link_withholding_move_lines()
            pay._justech_link_partial_reconciles()

    def _init_payments(self, to_process, edit_mode=False):
        payments = super()._init_payments(to_process, edit_mode=edit_mode)
        for payment, proc in zip(payments, to_process):
            self._justech_finalize_persistent_lines(payment, proc.get("batch"))
        return payments

    def _justech_stamp_gov_on_invoices(self, payments):
        """Delegado a extensión fiscal si está instalada."""
        stamp = getattr(payments, "_justech_stamp_gov_from_withholding", None)
        if stamp:
            stamp()

    def _reconcile_payments(self, to_process, edit_mode=False):
        super()._reconcile_payments(to_process, edit_mode=edit_mode)
        payments = self.env["account.payment"].concat(*[p["payment"] for p in to_process])
        payments._justech_link_withholding_move_lines()
        payments._justech_link_partial_reconciles()
        payments._justech_sync_application_lines()
        payments._justech_refresh_stored_totals()
        self._justech_stamp_gov_on_invoices(payments)
