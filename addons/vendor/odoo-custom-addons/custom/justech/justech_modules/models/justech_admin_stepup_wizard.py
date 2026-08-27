from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechAdminStepupWizard(models.TransientModel):
    _name = "justech.admin.stepup.wizard"
    _description = "Critical action step-up verification"

    admin_key = fields.Char(string="Justech Administrative Key", required=True)
    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    method_name = fields.Char(required=True)
    critical_action = fields.Char(required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.admin_key:
            raise UserError(_("Enter the Justech Administrative Key."))
        svc = self.env["justech.admin.access.service"]
        svc.verify_key_only(self.admin_key, action=self.critical_action)
        token = svc.issue_critical_grant(self.critical_action)
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_("Target record no longer exists."))
        return getattr(
            record.with_context(justech_critical_token=token),
            self.method_name,
        )()
