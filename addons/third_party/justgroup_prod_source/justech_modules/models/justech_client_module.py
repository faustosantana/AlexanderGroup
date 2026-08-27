from odoo import _, api, fields, models


class JustechClientModuleState(models.Model):
    _name = "justech.client.module.state"
    _description = "Client commercial module state per company"
    _rec_name = "product_id"

    product_id = fields.Many2one(
        "justech.commercial.product", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade", index=True
    )
    is_paid = fields.Boolean(default=False, index=True)
    is_blocked = fields.Boolean(default=False, index=True)
    origin = fields.Selection(
        [
            ("justech", "Justech"),
            ("marketplace", "Marketplace"),
            ("partner", "Partner"),
            ("client", "Cliente"),
        ],
        default="justech",
        index=True,
    )
    activated_at = fields.Datetime()
    activated_by_id = fields.Many2one("res.users", ondelete="set null")

    _justech_client_module_state_uniq = models.Constraint(
        "UNIQUE(product_id, company_id)",
        "Each commercial module can have only one state record per company.",
    )

    @api.model
    def get_or_create(self, product, company):
        state = self.sudo().search(
            [("product_id", "=", product.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if state:
            return state
        return self.sudo().create(
            {"product_id": product.id, "company_id": company.id}
        )


class JustechClientModuleFeatureFlag(models.Model):
    """Commercial/admin feature toggles per personalization (no fiscal enforcement)."""

    _name = "justech.client.module.feature.flag"
    _description = "Client Module Commercial Feature Flag"
    _rec_name = "feature_label"

    customization_code = fields.Char(required=True, index=True)
    feature_key = fields.Char(required=True, index=True)
    feature_label = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="cascade", index=True
    )
    is_active = fields.Boolean(default=True, index=True)
    control_type = fields.Selection(
        [("commercial", "Control comercial")],
        default="commercial",
        required=True,
    )

    _justech_feature_flag_uniq = models.Constraint(
        "UNIQUE(customization_code, feature_key, company_id)",
        "Each feature can have only one flag record per company.",
    )


class JustechClientModuleAudit(models.Model):
    _name = "justech.client.module.audit"
    _description = "Client Module Control Audit"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    company_id = fields.Many2one("res.company", ondelete="set null", index=True)
    ip_address = fields.Char()
    action = fields.Char(required=True, index=True)
    origin = fields.Selection(
        [
            ("justech", "Justech"),
            ("marketplace", "Marketplace"),
            ("partner", "Partner"),
            ("client", "Cliente"),
        ],
        default="justech",
        index=True,
    )
    product_code = fields.Char(index=True)
    commercial_name = fields.Char()
    client_name = fields.Char(string="Cliente", index=True)
    state_before = fields.Char()
    state_after = fields.Char()
    result = fields.Selection(
        [("success", "Success"), ("fail", "Fail")], default="success", index=True
    )
    reason = fields.Char()
    details = fields.Json(default=dict)
