from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechAdminCriticalGrant(models.Model):
    _name = "justech.admin.critical.grant"
    _description = "One-time critical action grant after step-up"
    _order = "id desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    action = fields.Char(required=True, index=True)
    token_hash = fields.Char(required=True, index=True)
    expires_at = fields.Datetime(required=True, index=True)

    @api.model
    def _gc_expired(self):
        self.sudo().search([("expires_at", "<", fields.Datetime.now())]).unlink()

    @api.model
    def issue(self, user, action, token):
        self._gc_expired()
        svc = self.env["justech.admin.access.service"]
        token_hash = svc._hash_critical_token(token)
        expires = fields.Datetime.now() + timedelta(seconds=60)
        self.sudo().create(
            {
                "user_id": user.id,
                "action": action,
                "token_hash": token_hash,
                "expires_at": expires,
            }
        )
        return token

    @api.model
    def consume(self, user, action, token):
        self._gc_expired()
        svc = self.env["justech.admin.access.service"]
        token_hash = svc._hash_critical_token(token)
        grant = self.sudo().search(
            [
                ("user_id", "=", user.id),
                ("action", "=", action),
                ("token_hash", "=", token_hash),
                ("expires_at", ">", fields.Datetime.now()),
            ],
            limit=1,
        )
        if not grant:
            return False
        grant.unlink()
        return True
