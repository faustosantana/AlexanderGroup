from odoo import models
from odoo.exceptions import AccessError


class JustechApprovalRequest(models.Model):
    _inherit = "justech.approval.request"

    def _mail_brand_label(self):
        self.ensure_one()
        return (self.company_id.name or "Alexander Group").upper()

    def write(self, vals):
        guarded = {"state", "decided_at", "decided_by_id"}
        if guarded & set(vals) and not self.env.su:
            raise AccessError(
                "No puede cambiar el estado de aprobación de forma directa."
            )
        return super().write(vals)

    def _can_decide(self, user=None, token_flow=False):
        user = user or self.env.user
        if (
            not self._is_approval_admin(user)
            and not self._user_rule_allows_request_type(
                user, self.company_id, self.request_type
            )
            and not user.has_group("justech_approval_flow.group_approver")
        ):
            raise AccessError("No tiene permiso para aprobar o rechazar.")
        return super()._can_decide(user=user, token_flow=token_flow)
