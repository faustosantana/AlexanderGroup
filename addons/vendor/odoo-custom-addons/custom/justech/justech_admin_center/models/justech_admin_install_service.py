import os
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminInstallService(models.AbstractModel):
    _name = "justech.admin.install.service"
    _description = "Instalación controlada de módulos Justech"

    @api.model
    def build_preview(self, module):
        module.ensure_one()
        if not module.technical_name.startswith("justech_"):
            raise UserError(_("Solo se pueden instalar módulos justech_* desde esta consola."))
        if module.technical_name.startswith("hellenia_") or "hellenia" in module.technical_name:
            raise UserError(_("Los módulos Hellenia no se instalan desde Administración Justech."))
        irm = module.ir_module_id or self.env["ir.module.module"].sudo().search(
            [("name", "=", module.technical_name)], limit=1
        )
        if not irm:
            raise UserError(_("El módulo no está en el catálogo de Odoo / addons."))
        if irm.state == "installed":
            raise UserError(_("El módulo ya está instalado."))

        to_install = irm + irm.upstream_dependencies(exclude_states=("installed", "uninstallable", "to remove"))
        justech_only = to_install.filtered(lambda m: m.name.startswith("justech_") or m.name in ("base", "web", "mail", "account"))
        # Still show full dependency list for transparency
        deps_lines = "\n".join("- %s (%s)" % (m.shortdesc or m.name, m.name) for m in to_install)
        risks = []
        if any(not n.startswith("justech_") and n not in ("base", "base_setup", "web", "mail", "account", "contacts", "sale", "purchase", "stock", "product", "portal", "accountant", "account_accountant", "l10n_do", "l10n_do_accounting", "account_debit_note") for n in to_install.mapped("name")):
            risks.append(_("Se instalarán dependencias no-Justech requeridas por Odoo."))
        risks.append(_("Se recomienda backup previo (automático en confirmación)."))
        risks.append(_("No se ejecutarán instalaciones concurrentes."))
        return {
            "before": _("Estado: no instalado"),
            "after": _("Estado: instalado (funcional inactivo hasta activar)"),
            "dependencies": deps_lines,
            "modules_to_install": to_install.mapped("name"),
            "risks": "\n".join(risks),
            "rollback": _("Restaurar backup BD+filestore del punto previo a la instalación."),
            "estimated_minutes": max(2, len(to_install)),
        }

    @api.model
    def execute(self, operation):
        self.env["justech.admin.center.auth.service"].require_session()
        module = operation.module_id
        if not module.technical_name.startswith("justech_"):
            raise UserError(_("Instalación no autorizada."))
        # Advisory lock — no concurrent installs
        self.env.cr.execute("SELECT pg_try_advisory_lock(%s)", [87201901])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            raise UserError(_("Ya hay una instalación Justech en curso. Espere a que finalice."))
        try:
            preview = self.build_preview(module)
            backup_path = self._create_backup(module.technical_name)
            operation.write(
                {
                    "backup_path": backup_path,
                    "preview_before": preview["before"],
                    "preview_after": preview["after"],
                    "risks": preview["risks"],
                    "rollback_notes": preview["rollback"],
                }
            )
            irm = module.ir_module_id.sudo()
            irm.button_immediate_install()
            self.env["justech.admin.registry.service"].discover_and_sync()
            module.invalidate_recordset()
            module = self.env["justech.admin.module"].browse(module.id)
            return {
                "ok": True,
                "message": _("Módulo %s instalado. Queda inactivo hasta activación funcional.")
                % module.functional_name,
                "backup_path": backup_path,
            }
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [87201901])


    @api.model
    def _create_backup(self, label):
        """Logical backup marker + optional dump when running on authorized DEV host."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        root = "/opt/odoo-dev/backups/jac-install-%s-%s" % (label, ts)
        try:
            os.makedirs(root, exist_ok=True)
            marker = os.path.join(root, "BACKUP_PATH.txt")
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write("module=%s\nts=%s\ndb=justech_dev\n" % (label, ts))
            # Best-effort dump (may fail without permissions — still record path intent)
            dump = os.path.join(root, "justech_dev.dump")
            rc = os.system("sudo -u odoo pg_dump -Fc justech_dev -f %s 2>/dev/null" % dump)
            if rc != 0:
                with open(marker, "a", encoding="utf-8") as fh:
                    fh.write("dump=SKIPPED_OR_FAILED\n")
            return root
        except OSError:
            return "logical-only:%s:%s" % (label, ts)
