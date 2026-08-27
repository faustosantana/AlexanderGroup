# -*- coding: utf-8 -*-
"""account.move — helper de lectura NCF vía Fiscal Data Provider."""
from __future__ import annotations

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def justech_get_ncf(self):
        """Único punto de lectura NCF para reportes/PDF/wizards."""
        self.ensure_one()
        return self.env["justech.do.fiscal.data.provider"].get_ncf(self)
