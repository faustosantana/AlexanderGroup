# -*- coding: utf-8 -*-
"""Post-migrate 19.0.1.16.1 — asegura catálogo clasificación fiscal persistido."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Model = env.get("justech.do.dgii.tax.classification")
    if Model is not None:
        Model.sync_from_taxes()
