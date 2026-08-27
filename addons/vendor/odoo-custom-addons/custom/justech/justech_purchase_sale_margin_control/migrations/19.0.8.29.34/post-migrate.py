# -*- coding: utf-8 -*-
"""19.0.8.29.34 — Restore app menu groups; UX cleanup PO/MTX."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_purchase_sale_margin_control.hooks import (
        ensure_margin_app_menu_restored,
        ensure_trace_so_supply_columns_hidden,
    )

    ensure_margin_app_menu_restored(env)
    ensure_trace_so_supply_columns_hidden(env)
