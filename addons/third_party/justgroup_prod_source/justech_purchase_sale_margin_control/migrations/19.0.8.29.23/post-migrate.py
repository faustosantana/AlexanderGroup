# -*- coding: utf-8 -*-
"""19.0.8.29.23 — Hide Trace SO purchase buttons; redirect link-existing to hub."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_purchase_sale_margin_control.hooks import (
        ensure_trace_invoice_buttons_hidden,
        ensure_trace_sale_buttons_hidden,
        redirect_trace_invoice_purchase_actions,
        redirect_trace_sale_purchase_actions,
    )

    redirect_trace_invoice_purchase_actions(env)
    redirect_trace_sale_purchase_actions(env)
    ensure_trace_invoice_buttons_hidden(env)
    ensure_trace_sale_buttons_hidden(env)
