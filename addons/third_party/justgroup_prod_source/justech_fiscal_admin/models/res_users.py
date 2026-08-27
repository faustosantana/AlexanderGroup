# -*- coding: utf-8 -*-
"""Roles fiscales Justech en el formulario de Usuarios (Odoo 19)."""
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    justech_fiscal_role = fields.Selection(
        [
            ("none", "Sin acceso fiscal"),
            ("user", "Usuario Fiscal"),
            ("officer", "Responsable Fiscal"),
            ("admin", "Administrador Fiscal"),
        ],
        string="Rol fiscal Justech",
        compute="_compute_justech_fiscal_role",
        inverse="_inverse_justech_fiscal_role",
        store=False,
        groups="base.group_system,justech_fiscal_admin.group_justech_fiscal_admin_manager",
    )
    justech_fiscal_company_ids = fields.Many2many(
        related="company_ids",
        string="Empresas fiscales permitidas",
        readonly=True,
    )
    justech_can_manage_padron = fields.Boolean(
        string="Administrar padrón DGII",
        compute="_compute_justech_fiscal_caps",
    )
    justech_can_manage_ranges = fields.Boolean(
        string="Administrar rangos",
        compute="_compute_justech_fiscal_caps",
    )
    justech_can_manage_withholding = fields.Boolean(
        string="Administrar retenciones",
        compute="_compute_justech_fiscal_caps",
    )
    justech_can_approve_fiscal = fields.Boolean(
        string="Aprobar revisión fiscal",
        compute="_compute_justech_fiscal_caps",
    )
    justech_can_run_diagnostics = fields.Boolean(
        string="Ejecutar diagnósticos",
        compute="_compute_justech_fiscal_caps",
    )

    def _justech_fiscal_group_xmlids(self):
        return {
            "user": "justech_l10n_do_base.group_justech_do_fiscal_user",
            "officer": "justech_l10n_do_base.group_justech_do_fiscal_manager",
            "admin": "justech_fiscal_admin.group_justech_fiscal_admin_manager",
        }

    @api.depends("group_ids")
    def _compute_justech_fiscal_role(self):
        for user in self:
            if user.has_group("justech_fiscal_admin.group_justech_fiscal_admin_manager"):
                user.justech_fiscal_role = "admin"
            elif user.has_group("justech_l10n_do_base.group_justech_do_fiscal_manager"):
                user.justech_fiscal_role = "officer"
            elif user.has_group("justech_l10n_do_base.group_justech_do_fiscal_user"):
                user.justech_fiscal_role = "user"
            else:
                user.justech_fiscal_role = "none"

    def _inverse_justech_fiscal_role(self):
        xmlids = self._justech_fiscal_group_xmlids()
        g_user = self.env.ref(xmlids["user"])
        g_officer = self.env.ref(xmlids["officer"])
        g_admin = self.env.ref(xmlids["admin"])
        for user in self:
            cmds = [(3, g_user.id), (3, g_officer.id), (3, g_admin.id)]
            role = user.justech_fiscal_role or "none"
            if role == "user":
                cmds.append((4, g_user.id))
            elif role == "officer":
                cmds.append((4, g_officer.id))
            elif role == "admin":
                cmds.append((4, g_admin.id))
            user.sudo().write({"group_ids": cmds})

    @api.depends("group_ids")
    def _compute_justech_fiscal_caps(self):
        for user in self:
            is_admin = user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            ) or user.has_group("base.group_system")
            is_officer = is_admin or user.has_group(
                "justech_l10n_do_base.group_justech_do_fiscal_manager"
            )
            user.justech_can_manage_padron = is_admin
            user.justech_can_manage_ranges = is_admin
            user.justech_can_manage_withholding = is_admin or user.has_group(
                "account.group_account_manager"
            )
            user.justech_can_approve_fiscal = is_officer
            user.justech_can_run_diagnostics = is_admin
