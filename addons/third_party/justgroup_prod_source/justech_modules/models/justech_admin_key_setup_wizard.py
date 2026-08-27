from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class JustechAdminKeySetupWizard(models.TransientModel):
    _name = "justech.admin.key.setup.wizard"
    _description = "Create Justech Administrative Key"

    admin_key = fields.Char(string="New Administrative Key", required=True)
    admin_key_confirm = fields.Char(string="Confirm Key", required=True)
    target_action_xmlid = fields.Char()
    scope = fields.Char(default="platform")

    def action_create_key(self):
        self.ensure_one()
        if self.admin_key != self.admin_key_confirm:
            raise ValidationError(_("Keys do not match."))
        svc = self.env["justech.admin.access.service"]
        access = svc.ensure_user_access()
        if access.has_key:
            raise UserError(_("You already have an administrative key. Use rotate instead."))
        access.set_key_hash(self.admin_key)
        svc._audit("setup_key", self.scope, True, svc._get_request_ip(), {})
        return {
            "type": "ir.actions.act_window",
            "name": _("Administrative Key Created"),
            "res_model": "justech.admin.key.display.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_one_time_key": self.admin_key,
                "default_one_time_message": _(
                    "Save this key now. It will not be shown again."
                ),
                "default_key_fingerprint": access.key_fingerprint,
                "default_target_action_xmlid": self.target_action_xmlid,
                "default_scope": self.scope,
            },
        }


class JustechAdminKeyDisplayWizard(models.TransientModel):
    _name = "justech.admin.key.display.wizard"
    _description = "One-time key display notice"

    one_time_key = fields.Char(readonly=True)
    one_time_message = fields.Char(readonly=True)
    key_fingerprint = fields.Char(readonly=True)
    target_action_xmlid = fields.Char()
    scope = fields.Char()

    def action_continue(self):
        self.ensure_one()
        if self.target_action_xmlid:
            return {
                "type": "ir.actions.act_window",
                "name": _("Justech Administrative Key"),
                "res_model": "justech.admin.key.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_scope": self.scope or "platform",
                    "default_target_action_xmlid": self.target_action_xmlid,
                },
            }
        return {"type": "ir.actions.act_window_close"}


class JustechAdminKeyRotateWizard(models.TransientModel):
    _name = "justech.admin.key.rotate.wizard"
    _description = "Rotate Justech Administrative Key"

    access_id = fields.Many2one("justech.admin.access", required=True)
    current_key = fields.Char(string="Current Key", required=True)
    new_key = fields.Char(string="New Key", required=True)
    new_key_confirm = fields.Char(string="Confirm New Key", required=True)

    def action_rotate(self):
        self.ensure_one()
        if self.new_key != self.new_key_confirm:
            raise ValidationError(_("New keys do not match."))
        svc = self.env["justech.admin.access.service"]
        svc.verify_key_only(self.current_key, action="rotate_key")
        self.access_id.set_key_hash(self.new_key)
        svc.revoke_all_sessions(user=self.access_id.user_id)
        svc._audit("rotate_key", "platform", True, svc._get_request_ip(), {})
        return {
            "type": "ir.actions.act_window",
            "name": _("Key Rotated"),
            "res_model": "justech.admin.key.display.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_one_time_key": self.new_key,
                "default_one_time_message": _(
                    "Key rotated. Save the new key now — it will not be shown again."
                ),
                "default_key_fingerprint": self.access_id.key_fingerprint,
            },
        }
