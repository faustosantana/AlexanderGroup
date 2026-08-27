# -*- coding: utf-8 -*-

from odoo import models


class JustechApprovalPolicyMixin(models.AbstractModel):
    _name = "justech.approval.policy.mixin"
    _description = "Política de bypass de aprobación Justech"

    def _justech_user_can_bypass_approval(self):
        """Admin (Settings) or explicit self-approval. Approvers do not bypass by default."""
        user = self.env.user
        if user.has_group("base.group_system"):
            return True
        rule = (
            self.env["justech.approval.user.rule"]
            .sudo()
            .search([("user_id", "=", user.id), ("active", "=", True)], limit=1)
        )
        return bool(rule and rule.allow_self_approval)

    def _justech_bypass_reason(self):
        if self.env.user.has_group("base.group_system"):
            return "admin"
        return "self"
