# -*- coding: utf-8 -*-
"""Install/upgrade hooks: forward-only effective datetime, no historical backfill."""

from odoo import fields


def _ensure_effective_from(env):
    """Set company effective datetime once; never rewrite historical bills."""
    Company = env["res.company"].sudo()
    now = fields.Datetime.now()
    for company in Company.search([("vendor_bill_approval_effective_from", "=", False)]):
        company.write({"vendor_bill_approval_effective_from": now})
        company.message_post(
            body=(
                "Política de facturas de proveedor: vigencia desde %s UTC. "
                "Aplica a facturas registradas a partir de la fecha de activación. "
                "Los documentos históricos conservan su flujo original."
            )
            % (now,)
        )


def post_init_hook(env):
    """Fresh install: stamp effective_from; do not enable strict or backfill approvals."""
    _ensure_effective_from(env)


def post_load_hook():
    """No-op placeholder for package documentation compatibility."""
    return None
