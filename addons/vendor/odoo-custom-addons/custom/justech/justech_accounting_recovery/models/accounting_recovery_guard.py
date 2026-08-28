# -*- coding: utf-8 -*-
"""Guard SoD — Recuperación Contable.

La cascada legítima se marca con un contador **thread-local**, nunca con
claves de ``context`` ORM. Orígenes que incrementan el contador:

1. ``account.bank.statement.line.action_undo_reconciliation`` (extracto / AML)
2. ``account.payment.unlink`` **después** de pasar el check de grupo
   (usuario autorizado; cualquier estado del pago)
3. ``authorized_reversal_enter`` tras validar permisos de Opción C
   (NC fiscal + Revertir factura) en el flujo atómico Justech

Así no puede activarse vía RPC, ``with_context``, server actions que solo
llaman métodos públicos, ni automatizaciones basadas en contexto.

``account.move.unlink``, ``account.payment.unlink``, ``button_draft``,
``button_cancel`` y ``_reverse_moves`` **sobre recordsets no vacíos**
exigen el grupo; omiten el check si ``in_payment_unlink_cascade()``,
``in_authorized_reversal()`` o si ``self`` está vacío (no-op ORM /
cascadas internas de Odoo, p.ej. ``account.payment.action_post`` →
``transactions._post_process()``).
"""
from __future__ import annotations

import threading

from odoo import _
from odoo.exceptions import AccessError

GROUP_ACCOUNTING_RECOVERY = "justech_accounting_recovery.group_accounting_recovery"

_payment_unlink_depth = threading.local()
_authorized_reversal_depth = threading.local()


def accounting_recovery_denied_message():
    return _(
        "No posee autorización para realizar operaciones de recuperación "
        "contable. Debe pertenecer al grupo «Recuperación Contable»."
    )


def authorized_reversal_enter():
    """Marca una reversión fiscal ya autorizada por Opción C / flujo atómico."""
    depth = getattr(_authorized_reversal_depth, "depth", 0)
    _authorized_reversal_depth.depth = depth + 1


def authorized_reversal_exit():
    depth = getattr(_authorized_reversal_depth, "depth", 0)
    _authorized_reversal_depth.depth = max(depth - 1, 0)


def in_authorized_reversal():
    return getattr(_authorized_reversal_depth, "depth", 0) > 0


def check_accounting_recovery(env):
    """Impide recuperación/reversión si el usuario no está en el grupo.

    Usa ``has_group`` sobre el usuario real (también bajo ``sudo()``:
    ``env.user`` no cambia). Sin excepción para Administrador.

    Excepción controlada: ``in_authorized_reversal()`` cuando Opción C ya
    validó permisos de NC fiscal + Revertir factura (sin sudo).
    """
    if in_authorized_reversal():
        return
    if not env.user.has_group(GROUP_ACCOUNTING_RECOVERY):
        raise AccessError(accounting_recovery_denied_message())


def payment_unlink_cascade_enter():
    depth = getattr(_payment_unlink_depth, "depth", 0)
    _payment_unlink_depth.depth = depth + 1


def payment_unlink_cascade_exit():
    depth = getattr(_payment_unlink_depth, "depth", 0)
    _payment_unlink_depth.depth = max(depth - 1, 0)


def in_payment_unlink_cascade():
    """True solo mientras corre una cascada armada por este módulo."""
    return getattr(_payment_unlink_depth, "depth", 0) > 0
