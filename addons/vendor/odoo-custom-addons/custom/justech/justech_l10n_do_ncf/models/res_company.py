# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    justech_do_fiscal_regularization_user_id = fields.Many2one(
        "res.users",
        string="Responsable de regularización fiscal",
        help="Usuario que recibe actividades al cancelar NCF "
        "(p. ej. Florangel Rodríguez). No hardcodear ID.",
    )


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _justech_find_fiscal_regularization_default(self):
        """Busca usuario por nombre (Florangel) sin hardcodear ID."""
        User = self.sudo()
        for domain in (
            [("name", "ilike", "Florangel Rodríguez")],
            [("name", "ilike", "Florangel Rodriguez")],
            [("name", "ilike", "Florangel")],
            [("login", "ilike", "florangel")],
        ):
            user = User.search(domain, limit=1)
            if user:
                return user
        return User.browse()
