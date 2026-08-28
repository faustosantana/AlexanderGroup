# -*- coding: utf-8 -*-
"""Etiquetas en español para estados y tipos visibles en UX/reportes."""
from odoo import _


PO_STATE_LABELS = {
    "draft": "Solicitud de cotización",
    "sent": "Solicitud enviada",
    "to approve": "Pendiente de aprobación",
    "purchase": "Orden de compra",
    "done": "Bloqueada",
    "cancel": "Cancelada",
}

INVOICE_STATE_LABELS = {
    "draft": "Borrador",
    "posted": "Contabilizada",
    "cancel": "Cancelada",
}

PAYMENT_STATE_LABELS = {
    "not_paid": "No pagada",
    "partial": "Pagada parcialmente",
    "in_payment": "En proceso de pago",
    "paid": "Pagada",
    "reversed": "Revertida",
    "invoicing_legacy": "Estado heredado",
    "legacy": "Estado heredado",
}

MOVE_TYPE_LABELS = {
    "in_invoice": "Factura de proveedor",
    "in_refund": "Nota de crédito de proveedor",
    "out_invoice": "Factura de cliente",
    "out_refund": "Nota de crédito de cliente",
}


def label_po_state(state):
    return _(PO_STATE_LABELS.get(state, state or ""))


def label_invoice_state(state):
    return _(INVOICE_STATE_LABELS.get(state, state or ""))


def label_payment_state(state):
    if not state:
        return ""
    return _(PAYMENT_STATE_LABELS.get(state, state))


def label_move_type(move_type):
    return _(MOVE_TYPE_LABELS.get(move_type, move_type or ""))
