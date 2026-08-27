# -*- coding: utf-8 -*-
"""19.0.8.29.37 — Integrity hotfix (DEV/UAT data repair) — RELEASE-SAFE NO-OP on PROD path.

Classification of the ORIGINAL migrate body (kept for audit, not executed):

A) STRUCTURAL: none
B) DEV/UAT repair: refresh known contaminated SOs
   CJO-0000736, CJO-0000735, CJO-0000699, CJO-0000685
C) MASS REFRESH: up to 80 open MTX with cost_estimated_amount > 0 via
   LineAllocationService.refresh_estimated_costs_from_live_assignments
D) OTHER: none

PROD rule (29.26 → 29.38):
  Do NOT rewrite historical commercial MTX costs on upgrade.
  DEV/UAT already applied the original refresh when they crossed 29.37;
  re-running it on PROD would alter live estimated costs without operator intent.

Opt-in (lab only): set env JUSTECH_MARGIN_29_37_REFRESH=1 before -u to restore
the original mass refresh behaviour. Never set this on PROD.
"""
import logging
import os

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    opt_in = os.environ.get("JUSTECH_MARGIN_29_37_REFRESH", "").strip() in (
        "1",
        "true",
        "True",
        "yes",
        "YES",
    )
    if not opt_in:
        _logger.info(
            "justech_purchase_sale_margin_control 19.0.8.29.37: "
            "SKIP mass MTX refresh (release-safe). "
            "Set JUSTECH_MARGIN_29_37_REFRESH=1 only for isolated lab repair."
        )
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if "purchase.sale.margin.transaction" not in env:
        return
    from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
        LineAllocationService,
    )

    svc = LineAllocationService(env)
    Tx = env["purchase.sale.margin.transaction"]
    sos = env["sale.order"].search(
        [("name", "in", ["CJO-0000736", "CJO-0000735", "CJO-0000699", "CJO-0000685"])]
    )
    txs = Tx.search([("sale_order_ids", "in", sos.ids)])
    txs |= Tx.search(
        [("state", "not in", ("closed", "rejected")), ("cost_estimated_amount", ">", 0)],
        limit=80,
    )
    n = 0
    for tx in txs:
        try:
            svc.refresh_estimated_costs_from_live_assignments(tx)
            n += 1
        except Exception as exc:  # noqa: BLE001
            _logger.warning("29.37 refresh skip %s: %s", tx.name, exc)
    _logger.info(
        "29.37 OPT-IN refreshed %s margin transactions from live assignments", n
    )
