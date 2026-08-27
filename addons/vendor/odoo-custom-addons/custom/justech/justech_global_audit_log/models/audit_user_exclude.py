from odoo import api, fields, models


class JustechAuditUserExclude(models.Model):
    _name = "justech.audit.user.exclude"
    _description = "Justech Audit User Exclude"
    _order = "user_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    active = fields.Boolean(default=True, index=True)
    reason = fields.Char()

    _justech_audit_user_exclude_uniq = models.Constraint(
        "UNIQUE(user_id)",
        "Este usuario ya está en la lista de exclusión.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["justech.audit.service"]._invalidate_runtime_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env["justech.audit.service"]._invalidate_runtime_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env["justech.audit.service"]._invalidate_runtime_cache()
        return result
