from odoo import fields, models


class JustechLicenseAudit(models.Model):
    _name = "justech.license.audit"
    _description = "Justech License Audit Log"
    _order = "create_date desc"

    action = fields.Selection(
        [
            ("register", "Register"),
            ("activate", "Activate"),
            ("deactivate", "Deactivate"),
            ("validate", "Validate"),
            ("revoke", "Revoke"),
            ("expire", "Expire"),
        ],
        required=True,
        index=True,
    )
    feature_id = fields.Many2one("justech.feature", ondelete="set null")
    license_id = fields.Many2one("justech.license", ondelete="set null")
    company_id = fields.Many2one("res.company", ondelete="set null", index=True)
    user_id = fields.Many2one("res.users", ondelete="set null", default=lambda self: self.env.uid)
    details = fields.Json()
