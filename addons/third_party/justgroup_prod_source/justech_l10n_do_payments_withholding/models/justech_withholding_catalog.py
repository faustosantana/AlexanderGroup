"""Catálogo configurable de retenciones RD — estándar Justech."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .withholding_account_validation import account_nature_label


class JustechDoWithholdingCatalog(models.Model):
    _name = "justech.do.withholding.catalog"
    _description = "Catálogo retenciones República Dominicana"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True, tracking=True)
    code = fields.Char(string="Código", required=True, index=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    date_from = fields.Date(string="Vigente desde", tracking=True)
    date_to = fields.Date(string="Vigente hasta", tracking=True)
    pending_confirmation = fields.Boolean(
        string="Pendiente de confirmación fiscal",
        default=False,
        tracking=True,
        help="Si está marcado, la retención no es utilizable en pagos hasta confirmación contable.",
    )
    company_config_ids = fields.One2many(
        "justech.do.withholding.company.config",
        "catalog_id",
        string="Configuración contable por empresa",
    )
    company_config_count = fields.Integer(compute="_compute_company_config_stats")
    company_config_pending_count = fields.Integer(compute="_compute_company_config_stats")
    # Cuenta efectiva en env.company (solo lectura UI)
    effective_company_id = fields.Many2one(
        "res.company",
        string="Empresa activa",
        compute="_compute_effective_account",
    )
    effective_account_id = fields.Many2one(
        "account.account",
        string="Cuenta efectiva",
        compute="_compute_effective_account",
    )
    effective_account_code = fields.Char(compute="_compute_effective_account")
    effective_account_nature = fields.Char(
        string="Naturaleza (empresa activa)",
        compute="_compute_effective_account",
    )
    effective_account_type = fields.Char(
        string="Tipo cuenta (empresa activa)",
        compute="_compute_effective_account",
    )
    effective_config_state = fields.Selection(
        [
            ("pending", "Pendiente de configurar"),
            ("configured", "Configurada"),
            ("invalid", "Configuración inválida"),
            ("inactive", "Inactiva"),
            ("missing", "Pendiente de configurar"),
        ],
        string="Estado",
        compute="_compute_effective_account",
    )
    effective_config_active = fields.Boolean(
        string="Activa en empresa activa",
        compute="_compute_effective_account",
    )
    effective_warning = fields.Char(
        string="Advertencia empresa activa",
        compute="_compute_effective_account",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=False,
        default=False,
        index=True,
        help=(
            "Vacío = retención global disponible para todas las empresas autorizadas. "
            "Con empresa = exclusivo de esa empresa (override opcional)."
        ),
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto retención",
        domain="[('amount', '<', 0)]",
        check_company=True,
        help=(
            "Impuesto l10n_do de la empresa (solo en retenciones específicas). "
            "En retenciones globales se resuelve por nombre al aplicar el pago."
        ),
    )
    source_tax_name = fields.Char(
        string="Nombre impuesto origen",
        help="Para catálogo global: nombre del impuesto l10n_do a resolver por empresa.",
        index=True,
    )
    source_tax_use = fields.Selection(
        [
            ("sale", "Ventas"),
            ("purchase", "Compras"),
            ("none", "Ninguno"),
        ],
        string="Uso impuesto origen",
        default="none",
    )
    withholding_type = fields.Selection(
        [
            ("isr", "ISR"),
            ("itbis", "ITBIS"),
            ("other", "Otro"),
        ],
        string="Tipo",
        required=True,
        default="isr",
    )
    rate = fields.Float(
        string="Porcentaje",
        tracking=True,
        help="Porcentaje nominal de retención (p. ej. 100 para ITBIS 100%, 30 para ITBIS 30%).",
    )
    base_type = fields.Selection(
        [
            ("untaxed", "Base imponible"),
            ("itbis", "ITBIS facturado"),
            ("total", "Total factura"),
            ("applied_amount", "Monto aplicado"),
        ],
        string="Base de cálculo",
        required=True,
        default="untaxed",
        help=(
            "Base imponible: subtotal sin impuestos. "
            "ITBIS facturado: monto ITBIS de la factura. "
            "Total factura: importe total. "
            "Monto aplicado: monto a pagar/cobrar en el wizard."
        ),
    )
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta contable (legado override)",
        compute="_compute_account_id",
        store=True,
        readonly=False,
        check_company=True,
        help=(
            "LEGADO: no usar para nuevas configuraciones. "
            "La cuenta operativa por empresa está en «Configuración contable por empresa»."
        ),
    )
    partner_scope = fields.Selection(
        [
            ("customer", "Cliente"),
            ("supplier", "Proveedor"),
            ("both", "Ambos"),
        ],
        string="Aplica a",
        required=True,
        default="both",
    )
    move_scope = fields.Selection(
        [
            ("sale", "Venta"),
            ("purchase", "Compra"),
            ("both", "Ambas"),
        ],
        string="Operación",
        required=True,
        default="both",
    )
    affects_606 = fields.Boolean(string="Afecta 606")
    affects_607 = fields.Boolean(string="Afecta 607")
    affects_623 = fields.Boolean(string="Afecta 623")
    dgii_withholding_code = fields.Char(
        string="Código retención DGII",
        help="Código para reportes DGII (606 col. T, Norma 2-05 col. H).",
        index=True,
        tracking=True,
    )
    tax_use = fields.Selection(
        related="tax_id.type_tax_use",
        string="Uso impuesto",
        store=True,
    )
    notes = fields.Text(string="Descripción / ayuda")

    _sql_constraints = []

    def init(self):
        """Único por (código, alcance empresa). COALESCE permite globales (company_id NULL)."""
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS justech_wh_catalog_code_scope_uniq
            ON justech_do_withholding_catalog (code, COALESCE(company_id, 0))
            """
        )

    @api.depends("company_config_ids", "company_config_ids.state", "company_config_ids.account_id")
    def _compute_company_config_stats(self):
        for rec in self:
            configs = rec.company_config_ids
            rec.company_config_count = len(configs)
            rec.company_config_pending_count = len(
                configs.filtered(lambda c: c.state == "pending" or not c.account_id)
            )

    @api.depends(
        "company_config_ids",
        "company_config_ids.account_id",
        "company_config_ids.active_config",
        "company_config_ids.state",
        "company_config_ids.warning_message",
    )
    def _compute_effective_account(self):
        company = self.env.company
        Config = self.env["justech.do.withholding.company.config"]
        for rec in self:
            rec.effective_company_id = company
            cfg = Config.search(
                [("catalog_id", "=", rec.id), ("company_id", "=", company.id)],
                limit=1,
            )
            if not cfg:
                rec.effective_account_id = False
                rec.effective_account_code = False
                rec.effective_account_nature = False
                rec.effective_account_type = False
                rec.effective_config_state = "missing"
                rec.effective_config_active = False
                rec.effective_warning = _(
                    "Esta retención no puede utilizarse en la empresa actual porque "
                    "no tiene una cuenta contable configurada."
                )
                continue
            rec.effective_account_id = cfg.account_id
            rec.effective_account_code = cfg.account_code
            rec.effective_account_nature = cfg.account_nature
            rec.effective_account_type = cfg.account_type or False
            rec.effective_config_state = cfg.state
            rec.effective_config_active = cfg.active_config
            if not cfg.account_id:
                rec.effective_warning = _(
                    "Esta retención no puede utilizarse en la empresa actual porque "
                    "no tiene una cuenta contable configurada."
                )
            elif not cfg.active_config:
                rec.effective_warning = _(
                    "Esta retención está configurada, pero permanece inactiva en la "
                    "empresa actual."
                )
            else:
                rec.effective_warning = cfg.warning_message or False

    def action_configure_active_company(self):
        """UX: abrir la configuración contable de la empresa activa (sin cambiar datos)."""
        self.ensure_one()
        company = self.env.company
        cfg = self.env["justech.do.withholding.company.config"].search(
            [("catalog_id", "=", self.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if not cfg:
            raise UserError(
                _(
                    "No existe configuración para %(wh)s en %(company)s. "
                    "Ejecute el asistente de configuración o cree la fila en la tabla inferior.",
                    wh=self.display_name,
                    company=company.display_name,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Cuenta contable — %s") % company.display_name,
            "res_model": "justech.do.withholding.company.config",
            "res_id": cfg.id,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_catalog_id": self.id,
                "default_company_id": company.id,
            },
        }

    def _get_withholding_account(self, company, date=None):
        """
        Servicio único de resolución de cuenta (fail-closed).

        No usa diario, banco, RET01/RET02, método de pago ni coincidencia por nombre.

        La config por empresa se lee con sudo controlado: el record rule multi-company
        filtra por ``allowed_company_ids`` (selector UI), y puede ocultar una config
        válida de ``document.company_id`` aunque el usuario sea miembro de esa empresa.
        """
        self.ensure_one()
        company = company or self.env.company
        if self.pending_confirmation:
            raise UserError(
                _(
                    "La retención «%(name)s» está pendiente de confirmación fiscal "
                    "y no puede utilizarse.",
                    name=self.display_name,
                )
            )
        if not self.active:
            raise UserError(
                _(
                    "La retención «%(name)s» está archivada y no puede utilizarse.",
                    name=self.display_name,
                )
            )
        if not self.env.su and company not in self.env.user.company_ids:
            raise UserError(
                _(
                    "No está autorizado a usar retenciones de %(company)s.",
                    company=company.display_name,
                )
            )
        # Lookup fiscal config: elevate read only (not payment/invoice).
        Config = self.env["justech.do.withholding.company.config"].sudo()
        domain = [
            ("catalog_id", "=", self.id),
            ("company_id", "=", company.id),
        ]
        cfg = Config.search(domain, limit=1)
        if not cfg:
            raise UserError(
                _(
                    "No existe configuración contable de «%(name)s» para %(company)s. "
                    "Configure la cuenta en Administrar Retenciones.",
                    name=self.display_name,
                    company=company.display_name,
                )
            )
        if not cfg.is_valid_for_use(date=date):
            if not cfg.account_id:
                raise UserError(
                    _(
                        "No puede utilizar %(wh)s en %(company)s porque no tiene "
                        "una cuenta contable válida configurada.",
                        wh=self.display_name,
                        company=company.display_name,
                    )
                )
            if not cfg.active_config:
                raise UserError(
                    _(
                        "La retención «%(name)s» está inactiva para %(company)s.",
                        name=self.display_name,
                        company=company.display_name,
                    )
                )
            raise UserError(
                _(
                    "La configuración de «%(name)s» para %(company)s no es válida "
                    "para la fecha indicada o la cuenta no está permitida.",
                    name=self.display_name,
                    company=company.display_name,
                )
            )
        # Account charts are company-scoped; bind company so code/name resolve.
        return cfg.account_id.with_company(company)

    @api.model
    def _search_payment_selectable(self, company, partner_type=None, move_scope=None, date=None):
        """Catálogos utilizables en wizard de pagos (activos, configurados, vigentes).

        No incluye pendientes de confirmación, inactivos, inválidos ni sin cuenta.
        """
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        if not self.env.su and company not in self.env.user.company_ids:
            return self.browse()
        domain = [
            ("active", "=", True),
            ("pending_confirmation", "=", False),
            ("code", "not in", ("RET-NONE", "wh_none")),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]
        if partner_type:
            domain.append(("partner_scope", "in", [partner_type, "both"]))
        if move_scope:
            domain.append(("move_scope", "in", [move_scope, "both"]))
        candidates = self.search(domain)
        Config = self.env["justech.do.withholding.company.config"].sudo()
        usable = self.browse()
        for cat in candidates:
            cfg = Config.search(
                [("catalog_id", "=", cat.id), ("company_id", "=", company.id)],
                limit=1,
            )
            if cfg and cfg.is_valid_for_use(date=date):
                usable |= cat
        return usable

    def get_payment_resolution_info(self, company, date=None):
        """Vista previa UI: empresa, cuenta, naturaleza, %, estado, vigencia.

        Fail-closed: exige configuración válida vía ``_get_withholding_account``.
        """
        self.ensure_one()
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        account = self._get_withholding_account(company, date=date)
        cfg = self.env["justech.do.withholding.company.config"].sudo().search(
            [("catalog_id", "=", self.id), ("company_id", "=", company.id)],
            limit=1,
        )
        return {
            "company_id": company.id,
            "company_name": company.display_name,
            "account_id": account.id,
            "account_code": account.code,
            "account_name": account.display_name,
            "account_nature": account_nature_label(account),
            "catalog_code": self.code,
            "catalog_name": self.name,
            "rate": self.rate,
            "state": cfg.state if cfg else False,
            "active_config": bool(cfg and cfg.active_config),
            "date_from": cfg.date_from if cfg else False,
            "date_to": cfg.date_to if cfg else False,
        }

    def resolve_for_payment(self, company, move, partner_type, applied_amount=None, date=None):
        """Único punto de resolución para wizards de pago (cuenta + monto).

        Toda cuenta sale de ``_get_withholding_account`` — sin diarios RET*/banco/fallback.
        """
        self.ensure_one()
        company = company or (move.company_id if move else self.env.company)
        date = date or fields.Date.context_today(self)
        if move and not self._applies_to_move(move, partner_type):
            raise UserError(
                _(
                    "La retención «%(name)s» no es compatible con esta operación "
                    "(%(partner)s / %(move)s).",
                    name=self.display_name,
                    partner=partner_type,
                    move=move.move_type,
                )
            )
        account = self._get_withholding_account(company, date=date)
        amount = self.compute_withholding_amount(move, applied_amount=applied_amount) if move else 0.0
        info = self.get_payment_resolution_info(company, date=date)
        return account, amount, info

    @api.model
    def ensure_company_configs(self, companies=None):
        """Bootstrap idempotente de configs por empresa para catálogo global."""
        catalogs = self.with_context(active_test=False).search([("company_id", "=", False)])
        return self.env["justech.do.withholding.company.config"].ensure_configs_for_companies(
            companies=companies, catalogs=catalogs
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        globals_created = records.filtered(lambda r: not r.company_id)
        if globals_created:
            self.env["justech.do.withholding.company.config"].ensure_configs_for_companies(
                catalogs=globals_created
            )
        return records

    @api.depends("tax_id", "tax_id.invoice_repartition_line_ids.account_id")
    def _compute_account_id(self):
        for rec in self:
            account = rec.account_id
            if rec.tax_id:
                rep = rec.tax_id.invoice_repartition_line_ids.filtered(
                    lambda l: l.repartition_type == "tax"
                )[:1]
                if rep.account_id:
                    account = rep.account_id
            rec.account_id = account

    @api.constrains("code", "company_id")
    def _check_code_scope_unique(self):
        for rec in self:
            domain = [("code", "=", rec.code), ("id", "!=", rec.id)]
            if rec.company_id:
                domain.append(("company_id", "=", rec.company_id.id))
            else:
                domain.append(("company_id", "=", False))
            if self.search_count(domain):
                scope = rec.company_id.display_name if rec.company_id else "global"
                raise ValidationError(
                    f"Ya existe una retención con código «{rec.code}» en alcance {scope}."
                )

    @api.constrains("active", "account_id", "code", "company_id", "rate", "source_tax_name")
    def _check_account_required(self):
        for rec in self:
            if not rec.active or rec.code in ("RET-NONE", "wh_none"):
                continue
            # Globales: la cuenta operativa vive en company.config (Fase 1).
            if not rec.company_id:
                if not rec.rate and not rec.source_tax_name and not rec.tax_id:
                    raise ValidationError(
                        f"La retención global «{rec.name}» necesita porcentaje o impuesto origen "
                        "para poder resolverse por empresa al aplicar el pago."
                    )
                continue
            if rec.company_id and not rec.account_id:
                raise ValidationError(
                    f"La retención «{rec.name}» (empresa {rec.company_id.display_name}) "
                    "debe tener cuenta contable antes de activarse."
                )

    def get_tax_for_company(self, company):
        """Resuelve impuesto de retención en la empresa operativa."""
        self.ensure_one()
        company = company or self.env.company
        if self.tax_id and (not self.tax_id.company_id or self.tax_id.company_id == company):
            return self.tax_id
        tax_name = self.source_tax_name or (self.tax_id.name if self.tax_id else False)
        if not tax_name:
            return self.env["account.tax"]
        domain = [
            ("name", "=", tax_name),
            ("company_id", "=", company.id),
            ("amount", "<", 0),
        ]
        if self.source_tax_use and self.source_tax_use != "none":
            domain.append(("type_tax_use", "=", self.source_tax_use))
        return self.env["account.tax"].search(domain, limit=1)

    def get_account_for_company(self, company):
        """LEGADO — solo sync/admin (tax repartition / account_id del catálogo).

        **Prohibido en pagos.** Wizards y asientos de pago deben usar
        ``_get_withholding_account`` / ``resolve_for_payment`` (Fase 2).
        """
        self.ensure_one()
        if self.env.context.get("justech_payment_withholding"):
            raise UserError(
                _(
                    "Resolución legado get_account_for_company bloqueada en pagos. "
                    "Use _get_withholding_account."
                )
            )
        company = company or self.env.company
        Account = self.env["account.account"]
        if self.account_id:
            account = self.account_id
            if "company_ids" in account._fields:
                if not account.company_ids or company in account.company_ids:
                    return account
            elif not account.company_id or account.company_id == company:
                return account
        tax = self.get_tax_for_company(company)
        if tax:
            rep = tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == "tax")[:1]
            if rep.account_id:
                return rep.account_id
        return Account

    def _itbis_amount(self, move):
        """Monto ITBIS positivo de la factura."""
        move.ensure_one()
        tax_lines = move.line_ids.filtered(
            lambda l: l.tax_line_id
            and l.tax_line_id.amount > 0
            and l.tax_line_id.type_tax_use in ("sale", "purchase")
        )
        if tax_lines:
            return abs(sum(tax_lines.mapped("balance")))
        return abs(move.amount_tax) if move.amount_tax else 0.0

    def _base_amount(self, move, applied_amount=None):
        self.ensure_one()
        if self.base_type == "itbis":
            return self._itbis_amount(move)
        if self.base_type == "total":
            return abs(move.amount_total)
        if self.base_type == "applied_amount":
            if applied_amount:
                return abs(applied_amount)
            return abs(move.amount_residual)
        return abs(move.amount_untaxed)

    def compute_withholding_amount(self, move, applied_amount=None):
        """Calcula monto retenido: base configurada × tasa nominal del catálogo.

        Pagos parciales: si se informa ``applied_amount`` y la base no es
        ``applied_amount``, se prorratea siempre contra el **total de la factura**
        (``amount_total``), no solo cuando el pago es menor que el residual.

        Motivo: si el último pago cubre todo el residual abierto, la condición
        antigua ``applied < residual`` no prorrateaba y aplicaba la base completa
        de la factura otra vez → sobre-retención acumulada.
        """
        self.ensure_one()
        rate = self.rate
        if not rate:
            tax = self.tax_id or self.get_tax_for_company(move.company_id)
            if tax:
                rate = abs(tax.amount)
        if not rate:
            return 0.0
        base = self._base_amount(move, applied_amount=applied_amount)
        if not base:
            return 0.0
        if applied_amount and self.base_type != "applied_amount":
            denom = abs(move.amount_total)
            if denom:
                base = base * (abs(applied_amount) / denom)
        return abs(rate / 100.0 * base)

    def _base_label(self):
        self.ensure_one()
        labels = {
            "untaxed": "Base imponible",
            "itbis": "ITBIS facturado",
            "total": "Total factura",
            "applied_amount": "Monto aplicado",
        }
        return labels.get(self.base_type, "Base")

    def _applies_to_move(self, move, partner_type):
        """Filtra por alcance configurado en catálogo (cliente/proveedor y operación)."""
        self.ensure_one()
        if self.partner_scope == "customer" and partner_type != "customer":
            return False
        if self.partner_scope == "supplier" and partner_type != "supplier":
            return False
        if self.move_scope == "sale" and move.move_type not in ("out_invoice", "out_refund"):
            return False
        if self.move_scope == "purchase" and move.move_type not in ("in_invoice", "in_refund"):
            return False
        return True

    @api.model
    def _legacy_code_map(self):
        """Migración upgrade-safe desde códigos Fase 18."""
        return {
            "RET-NONE": "wh_none",
            "RET-GOB-5": "wh_isr_gov",
            "RET-ITBIS-30": "wh_itbis_30",
            "RET-ITBIS-100": "wh_itbis_100",
            "RET-INF-ISR-10": "wh_isr_10",
            "RET-INF-ITBIS-75": "wh_itbis_75",
            "RET-ISR-2": "wh_isr_2",
            "RET-HON-10": "wh_isr_fees_10",
        }

    @api.model
    def _catalog_specs(self):
        """Especificación upgrade-safe — impuestos l10n_do documentados."""
        return [
            {
                "code": "RET-NONE",
                "legacy_code": "wh_none",
                "name": "Ninguna",
                "tax_name": False,
                "tax_use": False,
                "withholding_type": "isr",
                "base_type": "untaxed",
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": False,
                "affects_607": False,
                "active": False,
                "sequence": 0,
                "notes": "Opción por defecto: sin retenciones en la factura.",
            },
            {
                "code": "RET-GOB-5",
                "legacy_code": "wh_isr_gov",
                "name": "Retención 5% Gobierno",
                "tax_name": "-5% ISR Gov.",
                "tax_use": "sale",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 5.0,
                "partner_scope": "customer",
                "move_scope": "sale",
                "affects_606": False,
                "affects_607": True,
                "affects_623": True,
                "dgii_withholding_code": "07",
                "sequence": 10,
                "notes": "ISR 5% sobre base imponible — ventas a entidades gubernamentales (607).",
            },
            {
                "code": "RET-ITBIS-30",
                "legacy_code": "wh_itbis_30",
                "name": "Retención ITBIS 30%",
                "tax_name": "-30% ITBIS Leg. (N02-05)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 30.0,
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": True,
                "affects_607": True,
                "dgii_withholding_code": "02",
                "sequence": 20,
                "notes": "30% del ITBIS facturado — servicios legales N02-05.",
            },
            {
                "code": "RET-ITBIS-100",
                "legacy_code": "wh_itbis_100",
                "name": "Retención ITBIS 100%",
                "tax_name": "-100% ITBIS (N07-09)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 100.0,
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": True,
                "affects_607": True,
                "dgii_withholding_code": "03",
                "sequence": 25,
                "notes": "100% del ITBIS facturado — N07-09.",
            },
            {
                "code": "RET-INF-ISR-10",
                "legacy_code": "wh_isr_10",
                "name": "Retención ISR 10% Proveedor Informal",
                "tax_name": "-10% ISR Fee",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 10.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "dgii_withholding_code": "02",
                "sequence": 30,
                "notes": "ISR 10% sobre base imponible — proveedor informal (606).",
            },
            {
                "code": "RET-INF-ITBIS-75",
                "legacy_code": "wh_itbis_75",
                "name": "Retención ITBIS 75% Proveedor Informal",
                "tax_name": "-75% ITBIS (N08-10)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 75.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "dgii_withholding_code": "04",
                "sequence": 40,
                "notes": "75% del ITBIS facturado — proveedor informal N08-10 (606).",
            },
            {
                "code": "RET-ISR-2",
                "legacy_code": "wh_isr_2",
                "name": "Retención ISR 2%",
                "tax_name": "-2% ISR (N07-07)",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 2.0,
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": True,
                "affects_607": True,
                "dgii_withholding_code": "03",
                "sequence": 50,
                "notes": "ISR 2% sobre base imponible — N07-07.",
            },
            {
                "code": "RET-HON-10",
                "legacy_code": "wh_isr_fees_10",
                "name": "Retención ISR 10% Honorarios",
                "tax_name": "-10% ISR Rent.",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 10.0,
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": True,
                "affects_607": True,
                "dgii_withholding_code": "02",
                "sequence": 60,
                "notes": "ISR 10% sobre base imponible — honorarios y alquileres.",
            },
            # Retenciones adicionales l10n_do — inactivas hasta confirmación contable
            {
                "code": "RET-ITBIS-30-PROF",
                "name": "Retención ITBIS 30% Profesional",
                "tax_name": "-30% ITBIS Prof. (N02-05)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 30.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "active": False,
                "sequence": 70,
                "notes": "Variante profesional N02-05. Inactiva — confirmar con contabilidad antes de usar.",
                "pending_confirmation": True,
            },
            {
                "code": "RET-ITBIS-100-N01",
                "name": "Retención ITBIS 100% N01-11",
                "tax_name": "-100% ITBIS (N01-11)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 100.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "active": False,
                "pending_confirmation": True,
                "sequence": 75,
                "notes": "Norma N01-11. Inactiva — confirmar escenario contable.",
            },
            {
                "code": "RET-ITBIS-100-R293",
                "name": "Retención ITBIS 100% R293-11",
                "tax_name": "-100% ITBIS (R293-11)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 100.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "active": False,
                "pending_confirmation": True,
                "sequence": 76,
                "notes": "Norma R293-11. Inactiva — confirmar escenario contable.",
            },
            {
                "code": "RET-ISR-10-L253",
                "name": "Retención ISR 10% L253-12",
                "tax_name": "-10% ISR (L253-12)",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 10.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "active": False,
                "pending_confirmation": True,
                "sequence": 80,
                "notes": "Norma L253-12. Inactiva — confirmar escenario contable.",
            },
            {
                "code": "RET-ISR-2-MAT",
                "name": "Retención ISR 2% Materiales",
                "tax_name": "-2% ISR Mat.",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 2.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "active": False,
                "pending_confirmation": True,
                "sequence": 85,
                "notes": "ISR 2% materiales. Inactiva — confirmar escenario contable.",
            },
        ]

    @api.model
    def _uat_catalog_specs(self):
        """Specs DEMO/UAT — NUNCA en sync de Producción.

        Solo se materializan con context ``justech_sync_uat_withholdings`` o en tests.
        """
        return [
            {
                "code": "UAT-RET-ISR-2",
                "name": "UAT Retención ISR 2%",
                "tax_name": "-2% ISR (N07-07)",
                "tax_use": "purchase",
                "withholding_type": "isr",
                "base_type": "untaxed",
                "withholding_rate": 2.0,
                "partner_scope": "supplier",
                "move_scope": "purchase",
                "affects_606": True,
                "affects_607": False,
                "dgii_withholding_code": "03",
                "active": True,
                "sequence": 900,
                "notes": "DEMO DEV — catálogo de prueba. No usar en Producción.",
            },
            {
                "code": "UAT-RET-ITBIS-30",
                "name": "UAT Retención ITBIS 30%",
                "tax_name": "-30% ITBIS Leg. (N02-05)",
                "tax_use": "purchase",
                "withholding_type": "itbis",
                "base_type": "itbis",
                "withholding_rate": 30.0,
                "partner_scope": "both",
                "move_scope": "both",
                "affects_606": True,
                "affects_607": True,
                "dgii_withholding_code": "02",
                "active": True,
                "sequence": 910,
                "notes": "DEMO DEV — catálogo de prueba. No usar en Producción.",
            },
        ]

    @api.model
    def _find_catalog_record(self, spec, company=None):
        """Busca registro: preferir global; si company, también override de empresa."""
        Catalog = self.env["justech.do.withholding.catalog"].with_context(active_test=False)
        codes = [spec["code"]]
        if spec.get("legacy_code"):
            codes.append(spec["legacy_code"])
        # Global primero
        rec = Catalog.search([("code", "in", codes), ("company_id", "=", False)], limit=1)
        if rec or not company:
            return rec
        return Catalog.search([("code", "in", codes), ("company_id", "=", company.id)], limit=1)

    @api.model
    def _domain_for_payment(self, partner_type, move_type, company=None):
        """Dominio estándar: globales + override de la empresa activa."""
        company = company or self.env.company
        move_scope = "sale" if move_type in ("out_invoice", "out_refund") else "purchase"
        return [
            ("active", "=", True),
            ("code", "not in", ["RET-NONE", "wh_none"]),
            ("partner_scope", "in", [partner_type, "both"]),
            ("move_scope", "in", [move_scope, "both"]),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]

    @api.model
    def sync_catalog_from_taxes(self, company=None):
        """Sincroniza catálogo GLOBAL compartido (sin copias por empresa).

        ``company`` se usa solo para detectar si existen impuestos l10n_do de referencia
        y poder activar la ficha global cuando al menos una empresa DO tiene el impuesto.
        """
        company = company or self.env.company
        Tax = self.env["account.tax"]
        Catalog = self.env["justech.do.withholding.catalog"].with_context(active_test=False)
        result = []
        specs = list(self._catalog_specs())
        # UAT/DEMO: solo tests o sync explícito — nunca en post_init/migrate de Producción.
        from odoo.tools import config as odoo_config

        include_uat = bool(
            self.env.context.get("justech_sync_uat_withholdings")
            or odoo_config.get("test_enable")
        )
        if include_uat:
            specs.extend(self._uat_catalog_specs())
        for spec in specs:
            if str(spec.get("code") or "").startswith("UAT-") and not include_uat:
                continue
            tax = False
            tax_name = spec.get("tax_name")
            tax_use = spec.get("tax_use")
            if tax_name and tax_use:
                tax = Tax.search(
                    [
                        ("name", "=", tax_name),
                        ("type_tax_use", "=", tax_use),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                if not tax:
                    tax = Tax.search(
                        [
                            ("name", "=", tax_name),
                            ("type_tax_use", "=", tax_use),
                        ],
                        limit=1,
                    )
                if tax and not tax.active:
                    tax.active = True
            wants_active = spec.get("active", True)
            vals = {
                "name": spec["name"],
                "code": spec["code"],
                "sequence": spec.get("sequence", 10),
                "withholding_type": spec["withholding_type"],
                "base_type": spec["base_type"],
                "partner_scope": spec["partner_scope"],
                "move_scope": spec["move_scope"],
                "affects_606": spec["affects_606"],
                "affects_607": spec["affects_607"],
                "affects_623": spec.get("affects_623", False),
                "dgii_withholding_code": spec.get("dgii_withholding_code"),
                "notes": spec.get("notes"),
                "company_id": False,
                "tax_id": False,
                "source_tax_name": tax_name or False,
                "source_tax_use": tax_use or "none",
                "account_id": False,
                "rate": spec.get("withholding_rate") or (abs(tax.amount) if tax else 0.0),
                "active": False,
                "pending_confirmation": bool(spec.get("pending_confirmation")),
            }
            rec = self._find_catalog_record(spec, company=None)
            if rec:
                # No pisar overrides por empresa ni cuentas ya configuradas en globales legacy
                keep = {
                    "rate": rec.rate or vals["rate"],
                    "active": rec.active,
                }
                if rec.company_id:
                    # Existe solo override: crear global sin tocar override
                    rec = Catalog.create(vals)
                else:
                    write_vals = {k: v for k, v in vals.items() if k not in ("active",)}
                    if rec.account_id:
                        write_vals.pop("account_id", None)
                    if rec.tax_id:
                        write_vals.pop("tax_id", None)
                    rec.write(write_vals)
                    vals["rate"] = keep["rate"]
            else:
                rec = Catalog.create(vals)
            can_activate = wants_active and bool(vals["rate"] or tax or rec.source_tax_name)
            if rec.code in ("RET-NONE", "wh_none"):
                can_activate = False
            if can_activate and not rec.active:
                # Activar solo si alguna empresa puede resolver cuenta
                resolvable = bool(rec.get_account_for_company(company)) or bool(rec.rate)
                rec.write({"active": bool(resolvable and can_activate)})
            result.append(
                {
                    "code": spec["code"],
                    "id": rec.id,
                    "tax": tax.name if tax else rec.source_tax_name,
                    "active": rec.active,
                    "account": False,
                    "company_id": False,
                }
            )
        # Bootstrap configs pendientes para todas las empresas
        self.ensure_company_configs()
        return result
