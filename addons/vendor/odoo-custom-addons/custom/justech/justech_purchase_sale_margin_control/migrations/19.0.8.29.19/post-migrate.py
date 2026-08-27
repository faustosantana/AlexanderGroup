# -*- coding: utf-8 -*-
"""Recompute margin_band with sale-line cost coverage (provisional → pending).

NOTE: Only recompute txs that have sale orders. Coverage uses Trace
qty.assignment; ops without ASG become 'pending' by design (provisional).
Does not alter accounting documents.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Tx = env["purchase.sale.margin.transaction"]
    txs = Tx.search([("sale_order_ids", "!=", False)])
    _logger.info("29.19: recomputing margin_band for %s sale MTX", len(txs))
    # Invalidate then recompute so parent finance formula + coverage gate both run
    txs.invalidate_recordset(["margin_band"])
    txs._compute_margin_band()
