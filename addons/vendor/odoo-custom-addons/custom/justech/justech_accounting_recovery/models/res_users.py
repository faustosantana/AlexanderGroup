# -*- coding: utf-8 -*-
"""Autorización consolidada — Recuperación Contable / Corregir o Anular.

Única fuente de verdad para decidir si un usuario puede orquestar
corrección/anulación de documentos contables-fiscales por empresa.
"""
from odoo import _, models
from odoo.exceptions import AccessError

GROUP_ACCOUNTING_RECOVERY = "justech_accounting_recovery.group_accounting_recovery"

# Roles superiores / equivalentes (grupos opcionales: no fallar si el módulo
# no está instalado). No se eliminan grupos técnicos legacy.
_AUTHORIZED_GROUP_XMLIDS = (
    "base.group_system",
    "account.group_account_manager",
    GROUP_ACCOUNTING_RECOVERY,
    "justech_l10n_do_base.group_justech_do_fiscal_manager",
    "justech_fiscal_admin.group_justech_fiscal_admin_manager",
)


class ResUsers(models.Model):
    _inherit = "res.users"

    def _justech_has_group_safe(self, xmlid):
        """has_group tolerante a módulos/grupos no instalados."""
        self.ensure_one()
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return False
        return self.has_group(xmlid)

    def _justech_user_has_recovery_authority(self):
        """True si el usuario tiene Recuperación Contable o un rol superior."""
        self.ensure_one()
        return any(
            self._justech_has_group_safe(xmlid) for xmlid in _AUTHORIZED_GROUP_XMLIDS
        )

    def _justech_user_can_access_company(self, company):
        """Respeta company_ids del usuario y allowed companies del entorno."""
        self.ensure_one()
        if not company:
            return True
        company.ensure_one()
        if company not in self.company_ids:
            return False
        # env.companies = selector multiempresa (allowed_company_ids)
        if company not in self.env.companies:
            return False
        return True

    def can_recover_accounting_document(self, company=None):
        """Fuente única: ¿puede corregir/anular documentos en ``company``?

        No concede sudo. No asigna grupos. No abre empresas no autorizadas.
        """
        self.ensure_one()
        if company and not self._justech_user_can_access_company(company):
            return False
        return self._justech_user_has_recovery_authority()

    def assert_can_recover_accounting_document(self, company=None):
        """Raise AccessError estructurado si no está autorizado."""
        self.ensure_one()
        company_name = ""
        if company:
            company.ensure_one()
            company_name = company.display_name or company.name
            if not self._justech_user_can_access_company(company):
                raise AccessError(
                    _(
                        "PERMISO_EMPRESA|%(company)s|"
                        "Acceso a la empresa|"
                        "Empresas autorizadas del usuario"
                    )
                    % {"company": company_name}
                )
        if not self._justech_user_has_recovery_authority():
            raise AccessError(
                _(
                    "PERMISO_RECUPERACION|%(company)s|"
                    "Recuperación Contable|"
                    "Administrador Contable / Fiscal / Sistema"
                )
                % {"company": company_name or _("la empresa activa")}
            )
        return True
