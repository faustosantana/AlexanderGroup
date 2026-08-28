from odoo import api, models

from ..hooks import _setup_doralex_website


class Website(models.Model):
    _inherit = "website"

    @api.model
    def _dx_setup_public_site(self):
        _setup_doralex_website(self.env)
        return True
