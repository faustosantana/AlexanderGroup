from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminRoleAssignWizard(models.TransientModel):
    _name = "justech.admin.role.assign.wizard"
    _description = "Asignación de roles / matriz Justech"

    mode = fields.Selection(
        selection=[("assign", "Asignar rol"), ("matrix", "Matriz")],
        default="assign",
        required=True,
    )
    user_id = fields.Many2one("res.users")
    role_code = fields.Selection(
        selection=[
            ("justech_admin", "Administrador Justech"),
            ("fiscal_admin", "Administrador Fiscal"),
            ("fiscal_manager", "Responsable Fiscal"),
            ("fiscal_user", "Usuario Fiscal"),
            ("finance_admin", "Administrador Finanzas"),
            ("finance_user", "Usuario Finanzas"),
            ("warranty_manager", "Administrador Garantías"),
            ("warranty_user", "Usuario Garantías"),
            ("auditor", "Auditor"),
            ("readonly", "Solo lectura"),
        ],
        string="Rol",
    )
    role_explanation = fields.Char(compute="_compute_role_explanation", string="Este rol permite")
    preview_html = fields.Html(readonly=True)
    preview_before = fields.Text(readonly=True, string="Permisos actuales")
    preview_after = fields.Text(readonly=True, string="Permisos nuevos")
    confirmation = fields.Boolean(string="Confirmo el cambio de rol")

    @api.depends("role_code")
    def _compute_role_explanation(self):
        explain = {
            "justech_admin": "Administrar la consola Justech, productos, empresas y seguridad.",
            "fiscal_admin": "Administrar configuración fiscal, alertas y permisos fiscales.",
            "fiscal_manager": "Supervisar operación fiscal y revalidaciones.",
            "fiscal_user": "Operar funciones fiscales cotidianas.",
            "finance_admin": "Administrar cobros, pagos, tesorería y retenciones operativas.",
            "finance_user": "Operar cobros, pagos y tesorería.",
            "warranty_manager": "Administrar garantías, roles y parámetros.",
            "warranty_user": "Registrar y dar seguimiento a garantías.",
            "auditor": "Consultar auditoría y trazabilidad.",
            "readonly": "Solo lectura de información Justech.",
        }
        for wiz in self:
            wiz.role_explanation = explain.get(wiz.role_code or "", "")

    @api.onchange("user_id", "role_code")
    def _onchange_preview(self):
        if self.mode != "assign" or not self.user_id or not self.role_code:
            return
        data = self.env["justech.admin.permission.matrix.service"].apply_role(
            self.user_id, self.role_code, preview_only=True
        )
        self.preview_before = data.get("before")
        self.preview_after = data.get("after")

    def action_apply(self):
        self.ensure_one()
        if self.mode == "matrix":
            return {"type": "ir.actions.act_window_close"}
        if not self.confirmation:
            raise UserError(_("Confirme el cambio de rol."))
        # Protect last system admin
        if self.role_code != "justech_admin":
            sys_group = self.env.ref("base.group_system")
            if sys_group in self.user_id.all_group_ids:
                others = self.env["res.users"].sudo().search(
                    [("group_ids", "in", sys_group.id), ("id", "!=", self.user_id.id)]
                )
                if not others:
                    raise UserError(_("No se puede degradar al último Administrador del Sistema."))
        data = self.env["justech.admin.permission.matrix.service"].apply_role(
            self.user_id, self.role_code, preview_only=False
        )
        self.env["justech.admin.audit.log"].sudo().log_simple(
            summary=_("Rol %s → %s") % (self.user_id.login, self.role_code),
            operation="role_change",
            state_before=self.preview_before,
            state_after=self.preview_after,
            reason=_("Asignación desde Administración Justech"),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Rol actualizado"),
                "message": _("Usuario %s actualizado.") % self.user_id.login,
                "type": "success",
                "sticky": False,
            },
        }
