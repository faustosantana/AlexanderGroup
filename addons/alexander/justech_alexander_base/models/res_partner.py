from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _dx_is_company_partner(self):
        self.ensure_one()
        return bool(
            self.env["res.company"]
            .sudo()
            .search([("partner_id", "=", self.id)], limit=1)
        )
