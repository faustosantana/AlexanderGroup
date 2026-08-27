# -*- coding: utf-8 -*-
"""Post-migrate: sincroniza catálogo clasificación fiscal (upgrade)."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "justech.do.dgii.tax.classification" in env:
        env["justech.do.dgii.tax.classification"].sync_from_taxes()
