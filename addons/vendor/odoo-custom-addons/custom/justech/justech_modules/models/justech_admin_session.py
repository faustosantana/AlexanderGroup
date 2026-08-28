from datetime import timedelta

from odoo import api, fields, models


class JustechAdminSession(models.Model):
    _name = "justech.admin.session"
    _description = "Justech Admin Key Session"
    _order = "expires_at desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    scope = fields.Char(required=True, index=True)
    token_hash = fields.Char(required=True, index=True)
    expires_at = fields.Datetime(required=True, index=True)
    ip_address = fields.Char()
    active = fields.Boolean(default=True)

    @api.model
    def _session_minutes(self):
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_modules.admin_session_minutes", "15")
        )

    @api.model
    def create_session(self, user, scope, token_hash, ip_address=None):
        # Session rows are managed by the access service after key verification;
        # end users must not need direct CRUD ACL on justech.admin.session.
        Session = self.sudo()
        Session.search(
            [
                ("user_id", "=", user.id),
                ("scope", "=", scope),
                ("active", "=", True),
            ]
        ).write({"active": False})
        expires = fields.Datetime.now() + timedelta(minutes=self._session_minutes())
        return Session.create(
            {
                "user_id": user.id,
                "scope": scope,
                "token_hash": token_hash,
                "expires_at": expires,
                "ip_address": ip_address,
                "active": True,
            }
        )

    @api.model
    def find_valid(self, user, scope, token_hash):
        now = fields.Datetime.now()
        return self.sudo().search(
            [
                ("user_id", "=", user.id),
                ("scope", "=", scope),
                ("token_hash", "=", token_hash),
                ("active", "=", True),
                ("expires_at", ">", now),
            ],
            limit=1,
        )
