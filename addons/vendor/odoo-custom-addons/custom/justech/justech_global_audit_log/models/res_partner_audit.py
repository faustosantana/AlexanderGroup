from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_justech_open_audit_history(self):
        self.ensure_one()
        return self.env["justech.audit.log"].action_open_document_history(
            "res.partner", self.id, self.display_name
        )
