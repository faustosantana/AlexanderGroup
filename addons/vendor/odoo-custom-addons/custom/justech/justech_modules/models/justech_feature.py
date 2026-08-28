from odoo import fields, models


class JustechFeature(models.Model):
    _name = "justech.feature"
    _description = "Justech Commercial Feature"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    module_id = fields.Many2one("justech.module", ondelete="cascade", index=True)
    license_required = fields.Boolean(default=True)
    default_active = fields.Boolean(
        default=False,
        help="When licensed, activate by default for new company assignments.",
    )
    always_on = fields.Boolean(
        default=False,
        help="Platform features that do not require a license check.",
    )
    company_activation_ids = fields.One2many(
        "justech.feature.company",
        "feature_id",
        string="Company Activations",
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Feature code must be unique.",
    )
