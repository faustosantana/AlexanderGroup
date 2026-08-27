"""Wizard unificado cobro/pago con retenciones — estándar Justech."""
from __future__ import annotations

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class JustechPaymentPartnerWizardLine(models.TransientModel):
    _name = "justech.payment.partner.wizard.line"
    _description = "Línea factura pendiente — wizard pago Justech"

    wizard_id = fields.Many2one("justech.payment.partner.wizard", required=True, ondelete="cascade")
    move_id = fields.Many2one("account.move", required=True, ondelete="cascade")
    apply = fields.Boolean(string="Aplicar", default=False)
    invoice_name = fields.Char(related="move_id.name", string="Factura")
    ncf = fields.Char(compute="_compute_ncf", string="NCF")
    invoice_date = fields.Date(related="move_id.invoice_date", string="Fecha")
    date_maturity = fields.Date(compute="_compute_date_maturity", string="Vencimiento")
    currency_id = fields.Many2one(related="move_id.currency_id", string="Moneda")
    amount_total = fields.Monetary(related="move_id.amount_total", string="Total")
    amount_untaxed = fields.Monetary(related="move_id.amount_untaxed", string="Base imponible")
    amount_tax = fields.Monetary(related="move_id.amount_tax", string="ITBIS facturado")
    amount_residual = fields.Monetary(compute="_compute_amount_residual", string="Pendiente")
    amount_to_pay = fields.Monetary(string="Monto a aplicar", currency_field="currency_id", default=0.0)

    company_id = fields.Many2one(related="move_id.company_id", string="Compañía")
    move_scope_filter = fields.Selection(
        [("sale", "Venta"), ("purchase", "Compra")],
        compute="_compute_move_scope_filter",
        string="Operación factura",
    )
    withholding_catalog_ids = fields.Many2many(
        "justech.do.withholding.catalog",
        "justech_payment_wizard_line_wh_rel",
        "line_id",
        "catalog_id",
        string="Retenciones",
    )
    selectable_withholding_ids = fields.Many2many(
        "justech.do.withholding.catalog",
        compute="_compute_selectable_withholding_ids",
        string="Retenciones seleccionables",
    )
    withholding_summary = fields.Char(compute="_compute_withholding_display", string="Resumen retenciones")
    withholding_amount = fields.Monetary(
        compute="_compute_withholding_display", string="Total retenido", currency_field="currency_id"
    )
    withholding_detail_ids = fields.One2many(
        "justech.payment.withholding.wizard.line", "wizard_line_id", string="Detalle retenciones"
    )
    withholding_config_preview = fields.Text(
        compute="_compute_withholding_display",
        string="Configuración de retenciones",
    )
    net_after_withholding = fields.Monetary(
        compute="_compute_withholding_display", string="Neto a pagar/cobrar", currency_field="currency_id"
    )

    @api.depends(
        "move_id",
        "move_id.justech_do_ncf",
        "move_id.l10n_latam_document_number",
        "move_id.ref",
        "move_id.payment_reference",
        "move_id.name",
    )
    def _compute_ncf(self):
        fdp = self.env["justech.do.fiscal.data.provider"]
        for line in self:
            line.ncf = fdp.get_ncf(line.move_id) if line.move_id else ""

    @api.depends("move_id", "move_id.move_type")
    def _compute_move_scope_filter(self):
        for line in self:
            if line.move_id.move_type in ("out_invoice", "out_refund"):
                line.move_scope_filter = "sale"
            else:
                line.move_scope_filter = "purchase"

    @api.depends("move_id")
    def _compute_date_maturity(self):
        for line in self:
            aml = line.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            )[:1]
            line.date_maturity = aml.date_maturity if aml else line.move_id.invoice_date_due

    @api.depends("move_id", "move_id.amount_residual")
    def _compute_amount_residual(self):
        for line in self:
            line.amount_residual = abs(line.move_id.amount_residual)

    @api.depends(
        "company_id",
        "move_scope_filter",
        "apply",
        "wizard_id.partner_type",
        "wizard_id.payment_date",
    )
    def _compute_selectable_withholding_ids(self):
        Catalog = self.env["justech.do.withholding.catalog"]
        for line in self:
            if not line.apply or not line.company_id:
                line.selectable_withholding_ids = Catalog.browse()
                continue
            line.selectable_withholding_ids = Catalog._search_payment_selectable(
                company=line.company_id,
                partner_type=line._catalog_domain_partner_type(),
                move_scope=line.move_scope_filter,
                date=line.wizard_id.payment_date if line.wizard_id else None,
            )

    @api.depends(
        "withholding_catalog_ids",
        "withholding_detail_ids.amount",
        "withholding_detail_ids.account_code",
        "withholding_detail_ids.config_state",
        "amount_to_pay",
        "apply",
        "currency_id",
    )
    def _compute_withholding_display(self):
        for line in self:
            if not line.apply or not line.withholding_catalog_ids:
                line.withholding_summary = "Ninguna"
                line.withholding_amount = 0.0
                line.withholding_config_preview = False
                line.net_after_withholding = line.amount_to_pay if line.apply else 0.0
                continue
            labels = line.withholding_catalog_ids.mapped("name")
            line.withholding_summary = ", ".join(labels)
            partner_type = line._catalog_domain_partner_type()
            total = 0.0
            for catalog in line.withholding_catalog_ids:
                if not catalog._applies_to_move(line.move_id, partner_type):
                    continue
                total += catalog.compute_withholding_amount(
                    line.move_id, applied_amount=line.amount_to_pay
                )
            line.withholding_amount = total
            line.net_after_withholding = (line.amount_to_pay or 0.0) - total
            previews = []
            for wh in line.withholding_detail_ids:
                previews.append(
                    f"{wh.catalog_code or ''} {wh.label or ''} | "
                    f"Emp: {wh.company_id.display_name or '—'} | "
                    f"Cta: {wh.account_code or '—'} | "
                    f"Nat: {wh.account_nature or '—'} | "
                    f"%: {wh.rate} | Est: {wh.config_state or '—'} | "
                    f"Vig: {wh.date_from or '∞'}→{wh.date_to or '∞'}"
                )
            line.withholding_config_preview = "\n".join(previews) if previews else False

    @api.constrains("apply", "amount_to_pay")
    def _check_apply_amount_to_pay(self):
        for line in self:
            if not line.apply and (line.amount_to_pay or 0.0) > 0.01:
                raise ValidationError(
                    f"La factura {line.move_id.name} no está seleccionada; "
                    "el monto a aplicar debe ser cero."
                )

    @api.onchange("apply")
    def _onchange_apply(self):
        for line in self:
            if not line.apply:
                line.amount_to_pay = 0.0
                line.withholding_catalog_ids = [Command.clear()]
                line.withholding_detail_ids = [Command.clear()]
                continue
            if not line.amount_to_pay:
                line.amount_to_pay = line.amount_residual
            if line.withholding_catalog_ids:
                line._recompute_line_withholdings()

    @api.onchange("withholding_catalog_ids")
    def _onchange_withholding_catalog_ids(self):
        for line in self:
            if line.apply:
                line._recompute_line_withholdings()

    @api.onchange("amount_to_pay")
    def _onchange_amount_to_pay(self):
        for line in self:
            if not line.apply:
                line.amount_to_pay = 0.0
                continue
            if line.withholding_catalog_ids:
                line._recompute_line_withholdings()

    def _catalog_domain_partner_type(self):
        self.ensure_one()
        return self.wizard_id.partner_type if self.wizard_id else "customer"

    def _payment_resolution_date(self):
        self.ensure_one()
        return self.wizard_id.payment_date if self.wizard_id else fields.Date.context_today(self)

    def _recompute_line_withholdings(self):
        """Resuelve cuenta únicamente vía ``resolve_for_payment`` → ``_get_withholding_account``."""
        for line in self:
            if not line.move_id or not line.apply:
                line.withholding_detail_ids = [Command.clear()]
                continue
            partner_type = line._catalog_domain_partner_type()
            company = line.move_id.company_id or line.env.company
            payment_date = line._payment_resolution_date()
            details = [Command.clear()]
            for catalog in line.withholding_catalog_ids:
                account, amount, info = catalog.with_context(
                    justech_payment_withholding=True
                ).resolve_for_payment(
                    company=company,
                    move=line.move_id,
                    partner_type=partner_type,
                    applied_amount=line.amount_to_pay,
                    date=payment_date,
                )
                if not amount:
                    raise UserError(
                        f"La retención «{catalog.display_name}» resolvió monto cero "
                        f"para {line.move_id.name}. Revise base/porcentaje."
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
                            "base_amount": catalog._base_amount(
                                line.move_id, applied_amount=line.amount_to_pay
                            ),
                            "rate": catalog.rate,
                            "amount": amount,
                            "account_id": account.id,
                            "account_code": info.get("account_code"),
                            "account_nature": info.get("account_nature"),
                            "config_state": info.get("state"),
                            "date_from": info.get("date_from"),
                            "date_to": info.get("date_to"),
                            "currency_id": line.currency_id.id,
                        }
                    )
                )
            line.withholding_detail_ids = details


class JustechPaymentPartnerWizard(models.TransientModel):
    _name = "justech.payment.partner.wizard"
    _description = "Registrar cobro o pago con retenciones — Justech"

    partner_type = fields.Selection(
        [("customer", "Cliente"), ("supplier", "Proveedor")],
        required=True,
        default="customer",
    )
    partner_id = fields.Many2one("res.partner", string="Contacto", required=True)
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", default=lambda self: self.env.company.currency_id
    )
    line_ids = fields.One2many("justech.payment.partner.wizard.line", "wizard_id", string="Facturas pendientes")
    journal_id = fields.Many2one(
        "account.journal",
        domain="[('type', 'in', ('bank', 'cash')), ('code', 'not in', ('RET01', 'RET02'))]",
        string="Banco",
    )
    payment_method_line_id = fields.Many2one("account.payment.method.line", string="Método de pago")
    payment_date = fields.Date(default=fields.Date.context_today, string="Fecha de pago")
    communication = fields.Char(string="Concepto de pago")

    withholding_line_ids = fields.One2many(
        "justech.payment.withholding.wizard.line",
        "wizard_id",
        string="Detalle retenciones",
        compute="_compute_withholding_lines",
    )
    withholding_total = fields.Monetary(compute="_compute_totals", string="Total retenido", currency_field="currency_id")
    payment_total = fields.Monetary(compute="_compute_totals", string="Total a pagar/cobrar", currency_field="currency_id")
    amount_after_withholding = fields.Monetary(
        compute="_compute_totals", string="Neto a transferir", currency_field="currency_id"
    )

    justech_payment_reference = fields.Char(string="Referencia")
    justech_card_auth = fields.Char(string="Autorización")
    justech_card_batch = fields.Char(string="Lote")
    justech_check_number = fields.Char(string="Número de cheque")
    justech_check_bank_id = fields.Many2one("res.bank", string="Banco del cheque")
    justech_check_date = fields.Date(string="Fecha del cheque")
    justech_show_card_fields = fields.Boolean(compute="_compute_method_flags")
    justech_show_check_fields = fields.Boolean(compute="_compute_method_flags")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_type = self.env.context.get("default_partner_type") or res.get("partner_type") or "customer"
        partner_id = self.env.context.get("default_partner_id") or res.get("partner_id")
        if not partner_id and self.env.context.get("active_model") == "res.partner":
            partner_id = self.env.context.get("active_id")
        # Prefill desde factura(s) cuando se abre desde el botón de account.move
        if self.env.context.get("active_model") == "account.move":
            moves = self.env["account.move"].browse(self.env.context.get("active_ids") or [])
            moves = moves.filtered(lambda m: m.state == "posted" and m.is_invoice(include_receipts=True))
            if moves:
                move = moves[0]
                partner_id = partner_id or move.partner_id.id
                partner_type = (
                    "customer" if move.is_sale_document(include_receipts=True) else "supplier"
                )
                res.setdefault("currency_id", move.currency_id.id)
        res["partner_type"] = partner_type
        if partner_id:
            res["partner_id"] = partner_id
        currency = self.env.company.currency_id
        if self.env.context.get("default_currency_id"):
            currency = self.env["res.currency"].browse(self.env.context["default_currency_id"])
        res.setdefault("currency_id", currency.id)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            if wiz.partner_id and not wiz.line_ids:
                wiz._load_pending_invoices()
        return wizards

    @api.depends("line_ids.withholding_detail_ids")
    def _compute_withholding_lines(self):
        for wiz in self:
            wiz.withholding_line_ids = wiz.line_ids.mapped("withholding_detail_ids")

    @api.depends("payment_method_line_id.name")
    def _compute_method_flags(self):
        for wiz in self:
            name = (wiz.payment_method_line_id.name or "").lower()
            wiz.justech_show_card_fields = "tarjeta" in name
            wiz.justech_show_check_fields = "cheque" in name

    @api.depends("line_ids.amount_to_pay", "line_ids.apply", "line_ids.withholding_amount")
    def _compute_totals(self):
        for wiz in self:
            selected = wiz.line_ids.filtered("apply")
            wiz.payment_total = sum(selected.mapped("amount_to_pay"))
            wiz.withholding_total = sum(selected.mapped("withholding_amount"))
            wiz.amount_after_withholding = wiz.payment_total - wiz.withholding_total

    def _move_types(self):
        self.ensure_one()
        if self.partner_type == "customer":
            return ("out_invoice", "out_refund")
        return ("in_invoice", "in_refund")

    def _pending_invoice_domain(self):
        """Dominio de facturas pendientes (cobro/pago) para el wizard Justech."""
        self.ensure_one()
        commercial = self.partner_id.commercial_partner_id
        return [
            ("commercial_partner_id", "=", commercial.id),
            ("move_type", "in", self._move_types()),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("amount_residual", "!=", 0),
            ("company_id", "=", self.env.company.id),
        ]

    def _load_pending_invoices(self):
        self.ensure_one()
        if not self.partner_id:
            self.line_ids = [Command.clear()]
            return
        moves = self.env["account.move"].search(
            self._pending_invoice_domain(),
            order="invoice_date asc, id asc",
        )
        if self.currency_id:
            moves = moves.filtered(lambda m: m.currency_id == self.currency_id)
        preselect_ids = set(self.env.context.get("justech_preselect_move_ids") or [])
        if not preselect_ids and self.env.context.get("active_model") == "account.move":
            preselect_ids = set(self.env.context.get("active_ids") or [])
        lines = [Command.clear()]
        for move in moves:
            selected = move.id in preselect_ids
            lines.append(
                Command.create(
                    {
                        "move_id": move.id,
                        "apply": selected,
                        "amount_to_pay": abs(move.amount_residual) if selected else 0.0,
                    }
                )
            )
        self.line_ids = lines

    @api.onchange("partner_id", "partner_type", "currency_id")
    def _onchange_partner_load_invoices(self):
        self._load_pending_invoices()
        if self.partner_id and not self.line_ids:
            label = "cliente" if self.partner_type == "customer" else "proveedor"
            return {
                "warning": {
                    "title": "Sin facturas pendientes",
                    "message": (
                        f"No hay facturas pendientes del {label} en la empresa "
                        f"{self.env.company.display_name} "
                        f"y moneda {self.currency_id.display_name or '—'}. "
                        "Verifique la empresa activa y la moneda del pago."
                    ),
                }
            }

    @api.onchange("payment_method_line_id")
    def _onchange_payment_method_journal(self):
        if self.payment_method_line_id and self.payment_method_line_id.journal_id:
            self.journal_id = self.payment_method_line_id.journal_id

    @api.onchange("currency_id", "partner_type")
    def _onchange_currency_journal(self):
        if not self.currency_id:
            return
        Journal = self.env["account.journal"]
        journal = Journal.search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "=", self.env.company.id),
                ("currency_id", "=", self.currency_id.id),
            ],
            limit=1,
        )
        if not journal:
            journal = Journal.search(
                [
                    ("type", "in", ("bank", "cash")),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
        if journal:
            self.journal_id = journal
            lines = (
                journal.inbound_payment_method_line_ids
                if self.partner_type == "customer"
                else journal.outbound_payment_method_line_ids
            )
            transfer = lines.filtered(lambda l: "transferencia" in (l.name or "").lower())[:1]
            self.payment_method_line_id = transfer or lines[:1]

    @api.onchange("journal_id", "partner_type")
    def _onchange_journal_payment_method(self):
        if not self.journal_id:
            return
        lines = (
            self.journal_id.inbound_payment_method_line_ids
            if self.partner_type == "customer"
            else self.journal_id.outbound_payment_method_line_ids
        )
        if not self.payment_method_line_id or self.payment_method_line_id.journal_id != self.journal_id:
            transfer = lines.filtered(lambda l: "transferencia" in (l.name or "").lower())[:1]
            self.payment_method_line_id = transfer or lines[:1]

    def _register_vals_common(self):
        self.ensure_one()
        return {
            "journal_id": self.journal_id.id,
            "payment_method_line_id": self.payment_method_line_id.id,
            "payment_date": self.payment_date,
            "justech_payment_reference": self.justech_payment_reference,
            "justech_card_auth": self.justech_card_auth,
            "justech_card_batch": self.justech_card_batch,
            "justech_check_number": self.justech_check_number,
            "justech_check_bank_id": self.justech_check_bank_id.id,
            "justech_check_date": self.justech_check_date,
        }

    def _withholding_commands_for_line(self, line):
        line._recompute_line_withholdings()
        wh_total = sum(line.withholding_detail_ids.mapped("amount"))
        if wh_total and line.amount_to_pay < wh_total:
            raise UserError(
                f"La factura {line.move_id.name}: el monto retenido ({wh_total:.2f}) "
                f"supera el monto a aplicar ({line.amount_to_pay:.2f})."
            )
        commands = []
        for wh in line.withholding_detail_ids:
            if not wh.amount or not wh.account_id:
                continue
            commands.append(
                Command.create(
                    {
                        "wizard_line_id": line.id,
                        "catalog_id": wh.catalog_id.id,
                        "tax_id": wh.tax_id.id,
                        "label": wh.label,
                        "base_label": wh.base_label,
                        "base_amount": wh.base_amount,
                        "rate": wh.rate,
                        "amount": wh.amount,
                        "account_id": wh.account_id.id,
                        "currency_id": wh.currency_id.id,
                    }
                )
            )
        return commands

    def _validate_lines_for_register(self):
        self.ensure_one()
        self.env.flush_all()
        invalid_unselected = self.line_ids.filtered(lambda l: not l.apply and (l.amount_to_pay or 0.0) > 0.01)
        if invalid_unselected:
            names = ", ".join(invalid_unselected.mapped("move_id.name"))
            raise UserError(
                f"Facturas no seleccionadas con monto distinto de cero: {names}. "
                "Desmarque o ponga el monto en cero."
            )
        selected = self.line_ids.filtered(lambda l: l.apply and (l.amount_to_pay or 0.0) > 0)
        if not selected:
            raise UserError("Debe seleccionar al menos una factura con un monto mayor que cero.")
        for line in selected:
            residual = abs(line.move_id.amount_residual)
            if line.amount_to_pay > residual + 0.01:
                raise UserError(
                    f"El monto a aplicar ({line.amount_to_pay:.2f}) supera el pendiente "
                    f"de {line.move_id.name} ({residual:.2f})."
                )
        return selected

    def _validate_withholdings_phase2(self, selected):
        """Fail-closed: toda retención seleccionada debe resolver vía servicio único."""
        self.ensure_one()
        legacy_codes = {"RET01", "RET02"}
        jcode = (self.journal_id.code or "").upper()
        if jcode in legacy_codes:
            raise UserError(
                "No puede registrar pagos nuevos con diarios legado RET01/RET02. "
                "Use un diario de banco/caja operativo; la retención se contabiliza "
                "con la cuenta de company.config."
            )
        for line in selected:
            if not line.withholding_catalog_ids:
                continue
            # Re-resolver siempre antes de postear (bloquea si config inválida).
            line._recompute_line_withholdings()
            if len(line.withholding_detail_ids) != len(line.withholding_catalog_ids):
                raise UserError(
                    f"La factura {line.move_id.name}: no se pudieron resolver todas "
                    "las retenciones seleccionadas."
                )
            for wh in line.withholding_detail_ids:
                if not wh.account_id or not wh.amount:
                    raise UserError(
                        f"Retención inválida en {line.move_id.name}: falta cuenta o monto."
                    )
                # Re-check servicio único (sin usar account_id cacheado de forma ciega)
                resolved = wh.catalog_id._get_withholding_account(
                    line.move_id.company_id, date=self.payment_date
                )
                if resolved != wh.account_id:
                    raise UserError(
                        f"Inconsistencia de cuenta en {wh.label}: "
                        f"esperada {resolved.display_name}, obtenida {wh.account_id.display_name}."
                    )

    def _register_vals_for_line(self, line, common):
        """Legacy helper — una factura / un register (solo tests legacy)."""
        move = line.move_id
        applied = line.amount_to_pay
        residual = abs(move.amount_residual)
        is_partial = applied < residual - 0.01
        register_vals = {
            **common,
            "communication": self.communication or move.name,
            "amount": applied,
            "justech_withholding_line_ids": self._withholding_commands_for_line(line),
        }
        if is_partial:
            register_vals.update(
                {
                    "custom_user_amount": applied,
                    "custom_user_currency_id": line.currency_id.id,
                    "payment_difference_handling": "open",
                }
            )
        return register_vals, applied, is_partial

    def _assert_selected_compatible_for_single_payment(self, selected):
        """Rechaza agrupación silenciosa de documentos incompatibles."""
        self.ensure_one()
        companies = selected.mapped("move_id.company_id")
        if len(companies) > 1:
            raise UserError(
                "Las facturas seleccionadas pertenecen a distintas compañías. "
                "Regístrelas en pagos separados."
            )
        currencies = selected.mapped("move_id.currency_id")
        if len(currencies) > 1:
            raise UserError(
                "Las facturas seleccionadas tienen distintas monedas. "
                "Regístrelas en pagos separados."
            )
        partners = selected.mapped("move_id.commercial_partner_id")
        if len(partners) > 1:
            raise UserError(
                "Las facturas seleccionadas pertenecen a distintos partners comerciales. "
                "Regístrelas en pagos separados."
            )

    def _create_single_grouped_payment(self, selected):
        """Una intención de cobro/pago → un account.payment (N facturas).

        Reutiliza account.payment.register como motor interno con active_ids = N
        y group_payment forzado. No abre el wizard nativo al usuario.
        """
        self.ensure_one()
        self._assert_selected_compatible_for_single_payment(selected)

        moves = selected.mapped("move_id")
        total_applied = sum(selected.mapped("amount_to_pay"))
        currency = self.currency_id or moves[:1].currency_id
        sum_residual = sum(abs(m.amount_residual) for m in moves)
        is_partial = currency.compare_amounts(total_applied, sum_residual) < 0

        wh_commands = []
        for line in selected:
            wh_commands.extend(self._withholding_commands_for_line(line))

        common = self._register_vals_common()
        communication = self.communication or ", ".join(filter(None, moves.mapped("name")))
        register_vals = {
            **common,
            "communication": communication,
            "amount": total_applied,
            "group_payment": True,
            "justech_withholding_line_ids": wh_commands,
        }
        if is_partial:
            register_vals.update(
                {
                    "custom_user_amount": total_applied,
                    "custom_user_currency_id": currency.id,
                    "payment_difference_handling": "open",
                }
            )

        register_ctx = {
            "active_model": "account.move",
            "active_ids": moves.ids,
            "dont_redirect_to_payments": True,
            "justech_applied_amount": total_applied,
            "justech_force_group_payment": True,
        }
        if is_partial:
            register_ctx["force_payment_move"] = True

        Register = self.env["account.payment.register"]
        register = Register.with_context(**register_ctx).create(register_vals)
        write_vals = {
            "amount": total_applied,
            "group_payment": True,
        }
        if is_partial:
            write_vals.update(
                {
                    "custom_user_amount": total_applied,
                    "custom_user_currency_id": currency.id,
                    "payment_difference_handling": "open",
                }
            )
        register.write(write_vals)

        create_ctx = dict(register_ctx)
        if is_partial:
            create_ctx["force_payment_move"] = True
        payments = register.with_context(**create_ctx)._create_payments()
        if len(payments) != 1:
            raise UserError(
                f"Se esperaba 1 pago para {len(moves)} factura(s); "
                f"se crearon {len(payments)}. "
                "Revise diario, método, moneda y partner."
            )
        payments._justech_sync_application_lines()
        return payments

    def action_register_payments(self):
        self.ensure_one()
        if not self.journal_id or not self.payment_method_line_id:
            raise UserError("Indique banco (diario) y método de pago.")
        if not self.partner_id:
            raise UserError("Indique el contacto.")

        # Feature-flag lookup is admin metadata; accounting users must still pay.
        flags = self.env["justech.fiscal.feature.flag"].sudo()
        if flags.search_count([("code", "=", "payments_withholding")]):
            if not flags.is_enabled("payments_withholding", self.env.company):
                raise UserError(
                    "Pagos con retenciones desactivados en el Centro Fiscal. "
                    "Active el feature flag 'Pagos y Retenciones'."
                )

        selected = self._validate_lines_for_register()
        self._validate_withholdings_phase2(selected)
        if self.withholding_total and self.amount_after_withholding < 0:
            raise UserError("El total retenido supera el monto a aplicar.")

        payments = self._create_single_grouped_payment(selected)

        return {
            "type": "ir.actions.act_window",
            "name": "Pago registrado",
            "res_model": "account.payment",
            "res_id": payments.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
