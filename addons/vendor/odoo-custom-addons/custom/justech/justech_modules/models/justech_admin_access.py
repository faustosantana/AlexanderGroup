from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .justech_admin_key_util import fingerprint_from_hash, generate_admin_key, hash_admin_key


class JustechAdminAccess(models.Model):
    _name = "justech.admin.access"
    _description = "Justech Administrative Access"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    access_level = fields.Selection(
        [
            ("support", "Support"),
            ("manager", "Manager"),
            ("owner", "Owner"),
        ],
        default="manager",
        required=True,
    )
    key_hash = fields.Char(copy=False)
    key_fingerprint = fields.Char(compute="_compute_key_fingerprint", store=True)
    has_key = fields.Boolean(compute="_compute_has_key", store=True)
    last_verified_at = fields.Datetime()
    failed_attempts = fields.Integer(default=0)
    locked_until = fields.Datetime()
    allowed_modules = fields.Char(
        help="Optional comma-separated module codes; empty = all platform areas."
    )
    notes = fields.Text()

    _justech_admin_access_user_company_uniq = models.Constraint(
        "UNIQUE(user_id, company_id)",
        "Each user can have only one admin access record per company.",
    )

    @api.depends("key_hash")
    def _compute_key_fingerprint(self):
        for rec in self:
            rec.key_fingerprint = fingerprint_from_hash(rec.key_hash)

    @api.depends("key_hash")
    def _compute_has_key(self):
        for rec in self:
            rec.has_key = bool(rec.key_hash)

    @api.model
    def hash_key(self, key):
        return hash_admin_key(self.env, key)

    def verify_key(self, key):
        self.ensure_one()
        if not self.key_hash:
            return False, "not_configured"
        now = fields.Datetime.now()
        if self.locked_until and self.locked_until > now:
            return False, "locked"
        if hash_admin_key(self.env, key) != self.key_hash:
            failed = self.failed_attempts + 1
            max_fail = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("justech_modules.admin_key_max_failures", "5")
            )
            lock_min = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("justech_modules.admin_key_lock_minutes", "15")
            )
            vals = {"failed_attempts": failed}
            if failed >= max_fail:
                vals["locked_until"] = now + timedelta(minutes=lock_min)
            self.sudo().write(vals)
            return False, "locked" if failed >= max_fail else "invalid"
        self.sudo().write(
            {"failed_attempts": 0, "locked_until": False, "last_verified_at": now}
        )
        return True, "ok"

    @api.model
    def ensure_access_shell(self, user, company=None, access_level="manager"):
        """Create access record without a key — key must be set manually via wizard."""
        company = company or user.company_id
        access = self.sudo().search(
            [("user_id", "=", user.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if access:
            return access
        return self.sudo().create(
            {
                "user_id": user.id,
                "company_id": company.id,
                "access_level": access_level,
                "active": True,
                "key_hash": False,
            }
        )

    def set_key_hash(self, plain_key):
        """Store hash from manual setup/rotate wizard only."""
        self.ensure_one()
        if not plain_key or len(plain_key.strip()) < 8:
            raise ValidationError(_("Administrative key must be at least 8 characters."))
        self.sudo().write(
            {
                "key_hash": hash_admin_key(self.env, plain_key.strip()),
                "failed_attempts": 0,
                "locked_until": False,
                "active": True,
            }
        )

    def action_revoke_key(self):
        self.ensure_one()
        self.sudo().write(
            {
                "key_hash": False,
                "failed_attempts": 0,
                "locked_until": False,
            }
        )
        self.env["justech.admin.access.service"].revoke_all_sessions(
            user=self.user_id, scope=None
        )

    def action_block_access(self):
        self.ensure_one()
        self.sudo().write({"active": False})
        self.action_revoke_key()

    def action_open_rotate_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rotate Administrative Key"),
            "res_model": "justech.admin.key.rotate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_access_id": self.id},
        }

    def action_revoke_sessions(self):
        self.ensure_one()
        self.env["justech.admin.access.service"].revoke_all_sessions(user=self.user_id)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("key_plain") and not vals.get("key_hash"):
                vals["key_hash"] = hash_admin_key(self.env, vals.pop("key_plain"))
        return super().create(vals_list)

    @api.model
    def bootstrap_internal_users(self):
        from ..hooks import _setup_internal_admin_users

        _setup_internal_admin_users(self.env)

    @api.model
    def security_revoke_all_keys_and_sessions(self):
        """Hotfix: revoke every admin key and session (no plaintext logged)."""
        AccessSvc = self.env["justech.admin.access.service"]
        self.sudo().search([]).write(
            {
                "key_hash": False,
                "failed_attempts": 0,
                "locked_until": False,
            }
        )
        AccessSvc.revoke_all_sessions(scope=None, all_users=True)
        return True
