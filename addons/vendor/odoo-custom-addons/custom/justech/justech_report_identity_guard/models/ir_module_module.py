# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

BLOCKED_MODULES = frozenset({"justech_report_design", "hellenia_reports"})


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def button_immediate_install(self):
        self._jt_block_cross_brand_report_modules("install")
        return super().button_immediate_install()

    def button_install(self):
        self._jt_block_cross_brand_report_modules("install")
        return super().button_install()

    def _jt_block_cross_brand_report_modules(self, action):
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("justech_report_identity_guard.block_hellenia_modules", "1") != "1":
            return
        blocked = self.filtered(lambda m: m.name in BLOCKED_MODULES)
        if blocked:
            raise UserError(
                _(
                    "Instalación bloqueada: el módulo '%(name)s' redirige reportes "
                    "oficiales a plantillas Hellenia / Justech-brand y mezcla identidades "
                    "entre empresas. Justgroup requiere Odoo estándar + Studio + logo "
                    "por empresa. Anule el bloqueo solo con autorización expresa "
                    "(parámetro justech_report_identity_guard.block_hellenia_modules=0)."
                )
                % {"name": ", ".join(blocked.mapped("name"))}
            )
