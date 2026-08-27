# -*- coding: utf-8 -*-
"""No-op version bump: QWeb gate updated via data XML on module upgrade."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "justech_l10n_do_ncf 19.0.2.6.2: report gate XML reloaded on upgrade "
        "(is_l10n_do_invoice = company DO)"
    )
