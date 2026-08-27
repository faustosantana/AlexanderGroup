from odoo import api, models, _


class JustechAdminAccessServiceInherit(models.AbstractModel):
    _inherit = "justech.admin.access.service"

    @api.model
    def user_can_access_justech_settings(self, user=None):
        user = user or self.env.user
        if super().user_can_access_justech_settings(user=user):
            return True
        return user.has_group("justech_admin_center.group_justech_admin_center_manager")
