from odoo import api, models, _
from odoo.exceptions import UserError


class JustechAdminActivationService(models.AbstractModel):
    _name = "justech.admin.activation.service"
    _description = "Activación / desactivación funcional Justech"

    @api.model
    def build_preview(self, module, operation_type):
        module.ensure_one()
        if module.technical_state != "installed":
            raise UserError(_("El módulo debe estar instalado."))
        dependents = self.env["justech.admin.module"].search(
            [
                ("technical_state", "=", "installed"),
                ("functional_state", "=", "active"),
                ("dependency_names", "ilike", module.technical_name),
            ]
        )
        if operation_type == "deactivate":
            if module.is_critical and not dependents:
                # still allow with strong warning
                pass
            if dependents:
                raise UserError(
                    _(
                        "No se puede desactivar %(mod)s: depende(n) activo(s): %(deps)s",
                        mod=module.functional_name,
                        deps=", ".join(dependents.mapped("functional_name")),
                    )
                )
            if module.technical_name == "justech_admin_center":
                raise UserError(_("No se puede desactivar la propia consola de administración."))
            return {
                "before": _("Activo / en operación"),
                "after": _("Inactivo: sin nuevas operaciones; histórico conservado"),
                "risks": _("No se desinstala ni se borran tablas/campos/secuencias."),
                "rollback": _("Reactivar desde la consola."),
            }
        return {
            "before": _("Instalado inactivo / no configurado"),
            "after": _("Activo funcionalmente"),
            "risks": _("Verifique configuración por empresa antes de operar."),
            "rollback": _("Desactivar funcionalmente sin desinstalar."),
        }

    @api.model
    def activate(self, operation):
        module = operation.module_id
        self.build_preview(module, "activate")
        self._set_feature_flags(module, enabled=True)
        module.write({"functional_state": "active"})
        return {"ok": True, "message": _("Módulo activado: %s") % module.functional_name}

    @api.model
    def deactivate(self, operation):
        module = operation.module_id
        preview = self.build_preview(module, "deactivate")
        operation.write({"risks": preview["risks"], "rollback_notes": preview["rollback"]})
        self._set_feature_flags(module, enabled=False)
        module.write({"functional_state": "inactive"})
        return {"ok": True, "message": _("Módulo desactivado (datos conservados): %s") % module.functional_name}

    @api.model
    def _set_feature_flags(self, module, enabled):
        codes = [c.strip() for c in (module.feature_flag_codes or "").split(",") if c.strip()]
        if not codes or "justech.fiscal.feature.flag" not in self.env:
            return
        Flag = self.env["justech.fiscal.feature.flag"].sudo()
        flags = Flag.search([("code", "in", codes)])
        vals = {}
        if "is_enabled" in Flag._fields:
            vals["is_enabled"] = enabled
        elif "enabled" in Flag._fields:
            vals["enabled"] = enabled
        elif "active" in Flag._fields:
            vals["active"] = enabled
        if vals:
            flags.write(vals)
