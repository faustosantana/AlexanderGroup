from odoo.exceptions import ValidationError
from odoo import api, fields, models


class JustechAuditRule(models.Model):
    _name = "justech.audit.rule"
    _description = "Justech Audit Rule"
    _order = "model_description, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=False, index=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        required=True,
        ondelete="cascade",
        domain="[('transient', '=', False)]",
        index=True,
    )
    model_name = fields.Char(related="model_id.model", store=True, index=True)
    model_description = fields.Char(related="model_id.name", store=True)
    audit_create = fields.Boolean(string="Auditar creaciones", default=True)
    audit_write = fields.Boolean(string="Auditar modificaciones", default=True)
    audit_unlink = fields.Boolean(string="Auditar eliminaciones", default=True)
    company_ids = fields.Many2many(
        "res.company",
        "justech_audit_rule_company_rel",
        "rule_id",
        "company_id",
        string="Empresas",
        help="Vacío = aplica a todas las empresas.",
    )
    field_exclude_ids = fields.Many2many(
        "justech.audit.field.exclude",
        "justech_audit_rule_field_exclude_rel",
        "rule_id",
        "field_exclude_id",
        string="Campos excluidos adicionales",
        domain="['|', ('model_id', '=', False), ('model_id', '=', model_id)]",
    )
    notes = fields.Text()

    _justech_audit_rule_model_uniq = models.Constraint(
        "UNIQUE(model_id)",
        "Ya existe una regla para este modelo.",
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

    @api.constrains("model_id")
    def _check_model_not_technical(self):
        technical = self.env["justech.audit.service"].TECHNICAL_MODELS
        for rule in self:
            if rule.model_name in technical:
                raise ValidationError(
                    "Este modelo está excluido de la auditoría por diseño."
                )
