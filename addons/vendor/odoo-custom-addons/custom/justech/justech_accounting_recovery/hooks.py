# -*- coding: utf-8 -*-
"""Hooks de ciclo de vida del módulo."""


def uninstall_hook(env):
    """Restaura registros estándar tocados por este addon.

    La vista ``account_move_reversal_views.xml`` reemplaza ``group_ids`` de
    ``account.action_view_account_move_reversal``. Al desinstalar, Odoo no
    reaplica el XML de ``account``; aquí se restaura el valor original
    (``account.group_account_invoice``), dejando el sistema como antes de
    instalar este módulo.
    """
    action = env.ref(
        "account.action_view_account_move_reversal", raise_if_not_found=False
    )
    invoice_group = env.ref(
        "account.group_account_invoice", raise_if_not_found=False
    )
    if action is None or invoice_group is None:
        return
    action.write({"group_ids": [(6, 0, [invoice_group.id])]})
