# -*- coding: utf-8 -*-
"""19.0.8.29.38 — UX message Gestionar compras; Trace-compatible overalloc text.

Release path 29.26 → 29.38 (PROD):
  - 29.33–29.35: UI/menu structural hooks only
  - 29.36: no-op
  - 29.37: mass MTX refresh SKIPPED by default (see that migrate)
  - 29.38: log-only (this file)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "justech_purchase_sale_margin_control 19.0.8.29.38: "
        "pending-cost banner → Gestionar compras; Recalcular tooltip only. "
        "PROD path: no automatic commercial MTX rewrite."
    )
