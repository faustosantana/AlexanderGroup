# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import services
from . import report


def post_init_hook(env):
    from .hooks import (
        ensure_trace_invoice_buttons_hidden,
        ensure_trace_sale_buttons_hidden,
        ensure_trace_so_supply_columns_hidden,
        ensure_margin_app_menu_restored,
        ensure_margin_menu_groups_synced,
        redirect_trace_invoice_purchase_actions,
        redirect_trace_sale_purchase_actions,
    )

    redirect_trace_invoice_purchase_actions(env)
    redirect_trace_sale_purchase_actions(env)
    ensure_trace_invoice_buttons_hidden(env)
    ensure_trace_sale_buttons_hidden(env)
    ensure_trace_so_supply_columns_hidden(env)
    ensure_margin_menu_groups_synced(env)
    ensure_margin_app_menu_restored(env)
