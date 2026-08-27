# -*- coding: utf-8 -*-
"""19.0.1.5.4 — Activate multi-invoice payment menu; group_payment default."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref(
        "multi_invoice_manual_payment_prod.menu_multi_invoice_manual_payment_root",
        raise_if_not_found=False,
    )
    if menu and not menu.active:
        menu.active = True
