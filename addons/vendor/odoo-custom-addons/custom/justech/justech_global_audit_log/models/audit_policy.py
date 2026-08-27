from odoo import api, fields, models


class JustechAuditPolicy(models.Model):
    _name = "justech.audit.policy"
    _description = "Justech Audit Policy"
    _order = "company_id, id"

    name = fields.Char(required=True, default="Política de auditoría")
    active = fields.Boolean(default=False, index=True)
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        ondelete="cascade",
        index=True,
        help="Vacío = política global por defecto.",
    )
    audit_create = fields.Boolean(string="Auditar creaciones", default=True)
    audit_write = fields.Boolean(string="Auditar modificaciones", default=True)
    audit_unlink = fields.Boolean(string="Auditar eliminaciones", default=True)
    audit_events = fields.Boolean(
        string="Auditar eventos semánticos",
        default=True,
        help="Eventos de gobernanza, licencias e integraciones vía justech.audit.service.",
    )
    excluded_user_ids = fields.Many2many(
        "res.users",
        "justech_audit_policy_user_exclude_rel",
        "policy_id",
        "user_id",
        string="Usuarios excluidos",
    )
    notes = fields.Text()

    _justech_audit_policy_company_uniq = models.Constraint(
        "UNIQUE(company_id)",
        "Solo puede existir una política por empresa (incluida la global).",
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
