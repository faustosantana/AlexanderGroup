# -*- coding: utf-8 -*-

from odoo import models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_notify(self):
        approval_type = self.env.ref(
            "justech_approval_flow.mail_activity_approval",
            raise_if_not_found=False,
        )
        if approval_type:
            to_notify = self.filtered(lambda act: act.activity_type_id != approval_type)
            if not to_notify:
                return
            return super(MailActivity, to_notify).action_notify()
        return super().action_notify()
