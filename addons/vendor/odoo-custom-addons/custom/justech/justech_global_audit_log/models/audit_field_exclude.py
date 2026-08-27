from odoo import api, fields, models


class JustechAuditFieldExclude(models.Model):
    _name = "justech.audit.field.exclude"
    _description = "Justech Audit Field Exclude"
    _order = "model_id, field_name"

    name = fields.Char(required=True)
    field_name = fields.Char(required=True, index=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        ondelete="cascade",
        index=True,
        help="Vacío = exclusión global en todos los modelos.",
    )
    is_sensitive = fields.Boolean(
        default=True,
        help="Marca campos sensibles que deben enmascararse en logs.",
    )
    active = fields.Boolean(default=True)

    _justech_audit_field_exclude_uniq = models.Constraint(
        "UNIQUE(model_id, field_name)",
        "Este campo ya está excluido para el modelo indicado.",
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
