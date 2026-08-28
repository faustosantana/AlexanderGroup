from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_justech_open_admin_center(self):
        return self.env["justech.admin.console"].action_open_console()
