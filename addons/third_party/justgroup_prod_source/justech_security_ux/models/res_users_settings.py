# -*- coding: utf-8 -*-
"""Ensure res.users.settings always get a valid color_scheme on create.

Odoo 19 marks color_scheme required. The Usuarios → Nuevo web form (Invitado)
can create settings rows without the field, which blocks Guardar with a
validation error unrelated to Security UX permissions.
"""
from odoo import api, models


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("color_scheme"):
                vals["color_scheme"] = "system"
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "color_scheme" in vals and not vals.get("color_scheme"):
            vals["color_scheme"] = "system"
        return super().write(vals)
