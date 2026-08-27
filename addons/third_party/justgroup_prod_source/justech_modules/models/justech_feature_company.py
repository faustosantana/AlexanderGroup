from odoo import fields, models


class JustechFeatureCompany(models.Model):
    _name = "justech.feature.company"
    _description = "Feature Activation per Company"
    _order = "company_id, feature_id"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        ondelete="cascade",
        index=True,
    )
    feature_id = fields.Many2one(
        "justech.feature",
        required=True,
        ondelete="cascade",
        index=True,
    )
    is_active = fields.Boolean(default=False, index=True)
    activated_at = fields.Datetime()
    activated_by_id = fields.Many2one("res.users", ondelete="set null")

    _company_feature_unique = models.Constraint(
        "UNIQUE(company_id, feature_id)",
        "Feature activation must be unique per company.",
    )

    _feature_company_active_idx = models.Index(
        "(feature_id, company_id, is_active)"
    )
