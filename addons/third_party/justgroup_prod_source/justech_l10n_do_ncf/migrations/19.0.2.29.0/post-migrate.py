# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_l10n_do_ncf import _assign_fiscal_regularization_responsible

    _assign_fiscal_regularization_responsible(env)
