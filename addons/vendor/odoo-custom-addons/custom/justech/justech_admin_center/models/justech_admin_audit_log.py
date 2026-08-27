from odoo import api, fields, models


class JustechAdminAuditLog(models.Model):
    _name = "justech.admin.audit.log"
    _description = "Auditoría Administración Justech"
    _order = "id desc"
    _rec_name = "summary"

    summary = fields.Char(required=True)
    operation = fields.Char(required=True)
    module_id = fields.Many2one("justech.admin.module", ondelete="set null")
    operation_id = fields.Many2one("justech.admin.operation", ondelete="set null")
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    executed_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    company_ids = fields.Many2many("res.company")
    state_before = fields.Text()
    state_after = fields.Text()
    roles_before = fields.Text()
    roles_after = fields.Text()
    groups_before = fields.Text()
    groups_after = fields.Text()
    backup_path = fields.Char()
    result = fields.Selection(
        selection=[("ok", "OK"), ("error", "Error"), ("rollback", "Rollback")],
        default="ok",
        required=True,
    )
    error = fields.Text()
    rollback_info = fields.Text()
    reason = fields.Text()
    payload_json = fields.Text()

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            from odoo.exceptions import AccessError
            from odoo import _

            raise AccessError(_("Solo el Administrador del Sistema puede eliminar auditorías."))
        return super().unlink()

    @api.model
    def log_operation(self, operation, result):
        return self.create(
            {
                "summary": "%s — %s" % (operation.operation_type, operation.module_id.functional_name),
                "operation": operation.operation_type,
                "module_id": operation.module_id.id,
                "operation_id": operation.id,
                "company_ids": [(6, 0, operation.company_ids.ids)],
                "state_before": operation.preview_before,
                "state_after": operation.preview_after,
                "backup_path": result.get("backup_path") or operation.backup_path,
                "result": "ok" if result.get("ok", True) else "error",
                "error": result.get("message") if not result.get("ok", True) else False,
                "reason": operation.risks,
            }
        )

    @api.model
    def log_simple(self, **vals):
        vals.setdefault("user_id", self.env.user.id)
        vals.setdefault("executed_by", self.env.user.id)
        vals.setdefault("result", "ok")
        return self.create(vals)
