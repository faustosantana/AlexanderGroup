# -*- coding: utf-8 -*-
"""Log-only: SO Trace purchase header buttons hidden in 1.2.10 XML (hub owns UX)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "justech_sale_purchase_trace 19.0.1.2.10: hide Generar OC / Relacionar compra "
        "on sale.order header (methods kept for Gestionar compras hub)."
    )
