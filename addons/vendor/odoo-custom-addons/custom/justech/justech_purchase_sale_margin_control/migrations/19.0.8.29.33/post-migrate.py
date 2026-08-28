# -*- coding: utf-8 -*-
"""19.0.8.29.33 — PO→SO line dropdown fix; hide Trace SO supply columns."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_purchase_sale_margin_control.hooks import (
        ensure_trace_so_supply_columns_hidden,
    )

    ensure_trace_so_supply_columns_hidden(env)
