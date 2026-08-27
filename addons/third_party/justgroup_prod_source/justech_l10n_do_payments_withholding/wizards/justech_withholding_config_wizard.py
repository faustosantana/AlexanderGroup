# -*- coding: utf-8 -*-
"""Asistente: Configurar cuentas de retenciones."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.justech_l10n_do_payments_withholding.models.withholding_account_validation import (
    assert_withholding_account_allowed,
)


class JustechWithholdingConfigWizard(models.TransientModel):
    _name = "justech.withholding.config.wizard"
    _description = "Configurar cuentas de retenciones"

    company_id = fields.Many2one("res.company", string="Empresa")
    withholding_type = fields.Selection(
        [("isr", "ISR"), ("itbis", "ITBIS"), ("other", "Otro")],
        string="Tipo",
    )
    partner_scope = fields.Selection(
        [("customer", "Cliente"), ("supplier", "Proveedor"), ("both", "Ambos")],
        string="Aplica a",
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("configured", "Configurada"),
            ("invalid", "Inválida"),
            ("inactive", "Inactiva"),
        ],
        string="Estado",
    )
    active_only = fields.Boolean(string="Solo activas")
    line_ids = fields.Many2many(
        "justech.do.withholding.company.config",
        string="Configuraciones",
        compute="_compute_line_ids",
        readonly=False,
    )
    pending_count = fields.Integer(compute="_compute_line_ids")

    @api.depends("company_id", "withholding_type", "partner_scope", "state", "active_only")
    def _compute_line_ids(self):
        Config = self.env["justech.do.withholding.company.config"]
        for wiz in self:
            domain = []
            if wiz.company_id:
                domain.append(("company_id", "=", wiz.company_id.id))
            if wiz.withholding_type:
                domain.append(("withholding_type", "=", wiz.withholding_type))
            if wiz.partner_scope:
                domain.append(("partner_scope", "=", wiz.partner_scope))
            if wiz.state:
                domain.append(("state", "=", wiz.state))
            if wiz.active_only:
                domain.append(("active_config", "=", True))
            lines = Config.search(domain)
            wiz.line_ids = lines
            wiz.pending_count = Config.search_count(
                (domain if wiz.company_id else []) + [("state", "=", "pending")]
                if wiz.company_id
                else [("state", "=", "pending")]
            )

    def action_create_missing_configs(self):
        self.ensure_one()
        created = self.env["justech.do.withholding.catalog"].ensure_company_configs(
            companies=self.company_id or None
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuraciones"),
                "message": _("Creadas %(n)s configuraciones faltantes.", n=len(created)),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_configs(self):
        self.ensure_one()
        domain = []
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        if self.state:
            domain.append(("state", "=", self.state))
        return {
            "type": "ir.actions.act_window",
            "name": _("Configurar cuentas de retenciones"),
            "res_model": "justech.do.withholding.company.config",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_pending": 1},
        }
