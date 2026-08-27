# -*- coding: utf-8 -*-
"""Configuración contable de retención por empresa."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .withholding_account_validation import (
    account_nature_label,
    assert_withholding_account_allowed,
    nature_compatibility_warning,
)


class JustechDoWithholdingCompanyConfig(models.Model):
    _name = "justech.do.withholding.company.config"
    _description = "Configuración contable de retención por empresa"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id, catalog_id"
    _check_company_auto = True

    catalog_id = fields.Many2one(
        "justech.do.withholding.catalog",
        string="Retención",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        index=True,
        tracking=True,
    )
    account_id = fields.Many2one(
        "account.account",
        string="Cuenta contable",
        check_company=True,
        tracking=True,
        domain="[('active', '=', True)]",
    )
    date_from = fields.Date(string="Vigente desde", tracking=True)
    date_to = fields.Date(string="Vigente hasta", tracking=True)
    active_config = fields.Boolean(
        string="Activa",
        default=False,
        tracking=True,
        help="Solo las configuraciones activas con cuenta válida pueden usarse en pagos (Fase 2+).",
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente de configurar"),
            ("configured", "Configurada"),
            ("invalid", "Configuración inválida"),
            ("inactive", "Inactiva"),
        ],
        string="Estado",
        default="pending",
        required=True,
        tracking=True,
        compute="_compute_state",
        store=True,
        readonly=False,
    )
    notes = fields.Text(string="Observaciones", tracking=True)
    warning_message = fields.Char(
        string="Advertencia",
        compute="_compute_warning_and_nature",
    )
    account_code = fields.Char(
        related="account_id.code",
        string="Código",
    )
    account_name = fields.Char(
        related="account_id.name",
        string="Nombre cuenta",
    )
    account_type = fields.Selection(
        related="account_id.account_type",
        string="Tipo de cuenta",
    )
    account_nature = fields.Char(
        string="Naturaleza",
        compute="_compute_warning_and_nature",
    )
    catalog_code = fields.Char(related="catalog_id.code", string="Código retención", store=True)
    catalog_name = fields.Char(related="catalog_id.name")
    withholding_type = fields.Selection(related="catalog_id.withholding_type", store=True)
    rate = fields.Float(related="catalog_id.rate")
    partner_scope = fields.Selection(related="catalog_id.partner_scope")
    move_scope = fields.Selection(related="catalog_id.move_scope")
    pending_count_hint = fields.Boolean(
        compute="_compute_warning_and_nature",
        string="Pendiente",
    )

    _catalog_company_uniq = models.Constraint(
        "unique(catalog_id, company_id)",
        "Ya existe una configuración de esta retención para la empresa.",
    )

    @api.depends(
        "account_id",
        "account_id.account_type",
        "account_id.active",
        "active_config",
        "catalog_id",
        "company_id",
    )
    def _compute_warning_and_nature(self):
        for rec in self:
            rec.account_nature = account_nature_label(rec.account_id) if rec.account_id else ""
            rec.pending_count_hint = not rec.account_id
            warn = ""
            if not rec.account_id:
                warn = _("Sin cuenta configurada — no utilizable.")
            else:
                ok, _code, msg = assert_withholding_account_allowed(
                    rec.account_id, rec.company_id, raise_exception=False
                )
                if not ok:
                    warn = msg
                else:
                    warn = nature_compatibility_warning(rec.catalog_id, rec.account_id) or ""
            rec.warning_message = warn

    @api.depends(
        "account_id",
        "active_config",
        "account_id.active",
        "account_id.account_type",
        "company_id",
    )
    def _compute_state(self):
        for rec in self:
            if not rec.account_id:
                rec.state = "pending"
                continue
            ok, _code, _msg = assert_withholding_account_allowed(
                rec.account_id, rec.company_id, raise_exception=False
            )
            if not ok:
                rec.state = "invalid"
            elif not rec.active_config:
                rec.state = "inactive"
            else:
                rec.state = "configured"

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    _("La fecha «Vigente hasta» no puede ser anterior a «Vigente desde».")
                )

    @api.constrains("account_id", "company_id", "active_config")
    def _check_account_when_set(self):
        for rec in self:
            if rec.account_id:
                assert_withholding_account_allowed(rec.account_id, rec.company_id)

    def write(self, vals):
        activating = vals.get("active_config") is True
        if activating or "account_id" in vals:
            for rec in self:
                account = (
                    self.env["account.account"].browse(vals["account_id"])
                    if vals.get("account_id")
                    else rec.account_id
                )
                company = (
                    self.env["res.company"].browse(vals["company_id"])
                    if vals.get("company_id")
                    else rec.company_id
                )
                if activating:
                    if not account:
                        raise UserError(
                            _(
                                "No puede activar %(wh)s para %(company)s porque no tiene "
                                "una cuenta contable válida configurada.",
                                wh=rec.catalog_id.display_name,
                                company=company.display_name,
                            )
                        )
                    ok, _code, msg = assert_withholding_account_allowed(
                        account, company, raise_exception=False
                    )
                    if not ok:
                        raise UserError(
                            _(
                                "No puede activar %(wh)s para %(company)s: %(problem)s",
                                wh=rec.catalog_id.display_name,
                                company=company.display_name,
                                problem=msg,
                            )
                        )
                elif account:
                    assert_withholding_account_allowed(account, company)
        return super().write(vals)

    def action_activate(self):
        for rec in self:
            rec.write({"active_config": True})
        return True

    def action_deactivate(self):
        self.write({"active_config": False})
        return True

    def action_open_form(self):
        """UX: abrir esta configuración en formulario (desde la tabla por empresa)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configuración de cuenta"),
            "res_model": "justech.do.withholding.company.config",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def is_valid_for_use(self, date=None):
        self.ensure_one()
        if not self.active_config or not self.account_id:
            return False
        ok, _c, _m = assert_withholding_account_allowed(
            self.account_id, self.company_id, raise_exception=False
        )
        if not ok:
            return False
        if date:
            if self.date_from and date < self.date_from:
                return False
            if self.date_to and date > self.date_to:
                return False
        return True

    @api.model
    def ensure_configs_for_companies(self, companies=None, catalogs=None):
        """Idempotente: crea configs pendientes sin cuenta para cada par."""
        Company = self.env["res.company"]
        Catalog = self.env["justech.do.withholding.catalog"]
        companies = companies or Company.search([])
        catalogs = catalogs or Catalog.search([("company_id", "=", False)])
        created = self.browse()
        Config = self.sudo().with_context(active_test=False)
        for company in companies:
            for catalog in catalogs:
                existing = Config.search(
                    [
                        ("catalog_id", "=", catalog.id),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                self.env.cr.execute(
                    """
                    SELECT 1 FROM justech_do_withholding_company_config
                    WHERE catalog_id = %s AND company_id = %s
                    LIMIT 1
                    """,
                    (catalog.id, company.id),
                )
                if self.env.cr.fetchone():
                    continue
                try:
                    with self.env.cr.savepoint():
                        created |= self.create(
                            {
                                "catalog_id": catalog.id,
                                "company_id": company.id,
                                "account_id": False,
                                "active_config": False,
                                "notes": _("Creada automáticamente — pendiente de configurar."),
                            }
                        )
                except Exception as err:
                    err_name = type(err).__name__
                    if "Unique" not in err_name and "unique" not in str(err).lower():
                        raise
                    continue
        return created
