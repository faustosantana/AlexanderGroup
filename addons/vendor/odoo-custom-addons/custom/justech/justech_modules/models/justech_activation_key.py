from odoo import api, fields, models


class JustechActivationKey(models.Model):
    _name = "justech.activation.key"
    _description = "Justech Activation Key"
    _order = "create_date desc"

    key = fields.Char(required=True, index=True, copy=False)
    tier = fields.Selection(
        [
            ("TRIAL", "Trial"),
            ("STD", "Standard"),
            ("PRO", "Professional"),
            ("ENT", "Enterprise"),
        ],
        required=True,
        default="STD",
    )
    state = fields.Selection(
        [
            ("unused", "Unused"),
            ("used", "Used"),
            ("revoked", "Revoked"),
        ],
        default="unused",
        required=True,
        index=True,
    )
    license_id = fields.Many2one("justech.license", ondelete="set null")
    used_at = fields.Datetime()
    used_by_id = fields.Many2one("res.users", ondelete="set null")

    _key_unique = models.Constraint(
        "UNIQUE(key)",
        "Activation key must be unique.",
    )

    @api.model
    def _generate_key(self, tier="STD"):
        import secrets

        token = secrets.token_hex(6).upper()
        return f"JT-{tier}-{token}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("key"):
                vals["key"] = self._generate_key(vals.get("tier", "STD"))
        return super().create(vals_list)
