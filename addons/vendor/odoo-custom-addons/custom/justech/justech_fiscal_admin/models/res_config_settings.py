# -*- coding: utf-8 -*-
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_justech_open_fiscal_admin_center(self):
        return self.env["justech.fiscal.admin.center"].open_for_user()

    def action_justech_open_fiscal_feature_flags(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Feature Flags Fiscales",
            "res_model": "justech.fiscal.feature.flag",
            "view_mode": "list,form",
        }
