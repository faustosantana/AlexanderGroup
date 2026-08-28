from odoo import api, models, _
from odoo.exceptions import UserError


ROLE_CATALOG = [
    ("justech_admin", "Administrador Justech", ["justech_admin_center.group_justech_admin_center_manager"]),
    ("fiscal_admin", "Administrador Fiscal", ["justech_fiscal_admin.group_justech_fiscal_admin_manager"]),
    ("fiscal_manager", "Responsable Fiscal", ["justech_l10n_do_base.group_justech_do_fiscal_manager"]),
    ("fiscal_user", "Usuario Fiscal", ["justech_l10n_do_base.group_justech_do_fiscal_user"]),
    ("ecf_admin", "Administrador e-CF", ["justech_ecf_core.group_ecf_admin"]),
    ("ecf_responsible", "Responsable e-CF", ["justech_ecf_core.group_ecf_responsible"]),
    ("ecf_operator", "Operador e-CF", ["justech_ecf_core.group_ecf_operator"]),
    ("ecf_readonly", "Solo lectura e-CF", ["justech_ecf_core.group_ecf_readonly"]),
    ("finance_admin", "Administrador Finanzas", []),
    ("finance_user", "Usuario Finanzas", []),
    ("warranty_manager", "Administrador Garantías", ["justech_warranty.group_warranty_manager"]),
    ("warranty_user", "Usuario Garantías", ["justech_warranty.group_warranty_user"]),
    ("auditor", "Auditor", ["justech_global_audit_log.group_justech_audit_manager", "justech_global_audit_log.group_audit_user"]),
    ("readonly", "Solo lectura", []),
]


ROLE_EXPLAIN = {
    "justech_admin": "Administrar la consola Justech, productos, empresas y seguridad.",
    "fiscal_admin": "Administrar Centro Fiscal, NCF, e-CF, padrón, reportes y retenciones.",
    "fiscal_manager": "Revisar, aprobar y diagnosticar sin cambiar secretos críticos.",
    "fiscal_user": "Operar y consultar funciones fiscales cotidianas.",
    "ecf_admin": "Configurar empresas e-CF, certificados, ambientes, asistentes, colas y certificación.",
    "ecf_responsible": "Operar y supervisar e-CF; ejecutar validaciones sin modificar secretos críticos.",
    "ecf_operator": "Emitir y gestionar documentos e-CF en ambientes permitidos.",
    "ecf_readonly": "Consultar e-CF sin modificar.",
    "finance_admin": "Administrar cobros, pagos, tesorería y retenciones operativas.",
    "finance_user": "Operar cobros, pagos y tesorería.",
    "warranty_manager": "Administrar garantías, roles y parámetros.",
    "warranty_user": "Registrar y dar seguimiento a garantías.",
    "auditor": "Consultar auditoría y trazabilidad.",
    "readonly": "Solo lectura de información Justech.",
}

ROLE_SECTIONS = [
    ("admin", "Administración Justech", ["justech_admin"]),
    ("fiscal", "Fiscal", ["fiscal_user", "fiscal_manager", "fiscal_admin"]),
    ("ecf", "e-CF", ["ecf_readonly", "ecf_operator", "ecf_responsible", "ecf_admin"]),
    ("finance", "Finanzas", ["finance_user", "finance_admin"]),
    ("warranty", "Garantías", ["warranty_user", "warranty_manager"]),
    ("audit", "Auditoría", ["auditor", "readonly"]),
]


class JustechAdminPermissionMatrixService(models.AbstractModel):
    _name = "justech.admin.permission.matrix.service"
    _description = "Matriz de permisos funcionales Justech"

    @api.model
    def role_catalog(self):
        rows = []
        for code, label, xmlids in ROLE_CATALOG:
            group = self._resolve_group(xmlids)
            rows.append(
                {
                    "code": code,
                    "label": label,
                    "group": group,
                    "available": bool(group) or code in ("readonly", "finance_admin", "finance_user"),
                    "explain": ROLE_EXPLAIN.get(code, ""),
                }
            )
        return rows

    @api.model
    def _resolve_group(self, xmlids):
        for xid in xmlids:
            try:
                return self.env.ref(xid)
            except ValueError:
                continue
        return self.env["res.groups"]

    @api.model
    def render_html(self):
        roles_by_code = {r["code"]: r for r in self.role_catalog()}
        parts = ['<div class="o_jac_matrix">']
        for section_code, section_label, codes in ROLE_SECTIONS:
            parts.append('<div class="o_jac_matrix_section"><h4>%s</h4>' % section_label)
            parts.append(
                '<table class="table table-sm o_jac_table"><thead><tr>'
                "<th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>"
                % (_("Rol"), _("Disponible"), _("Este rol permite"))
            )
            for code in codes:
                role = roles_by_code.get(code)
                if not role:
                    continue
                parts.append(
                    "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (
                        role["label"],
                        _("Sí") if role["available"] else _("Pendiente"),
                        role.get("explain") or ROLE_EXPLAIN.get(code, ""),
                    )
                )
            parts.append("</tbody></table></div>")
        parts.append("</div>")
        return "".join(parts)

    @api.model
    def apply_role(self, user, role_code, preview_only=False):
        """Map functional role to groups — additive, never silent."""
        catalog = {r["code"]: r for r in self.role_catalog()}
        role = catalog.get(role_code)
        if not role:
            return {"ok": False, "message": _("Rol desconocido")}
        before = user.group_ids.mapped("display_name")
        group = role["group"]
        after_groups = user.group_ids
        if group:
            after_groups = after_groups | group
        if preview_only:
            return {
                "ok": True,
                "before": ", ".join(before),
                "after": ", ".join((after_groups).mapped("display_name")),
                "group": group,
            }
        # Escritura de roles funcionales: única vía = pestaña Permisos
        raise UserError(
            _(
                "apply_role deshabilitado. Asigne grupos desde la pestaña "
                "«Permisos» del formulario de usuario."
            )
        )
