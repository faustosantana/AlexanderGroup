# -*- coding: utf-8 -*-
"""QWeb-only hotfix: company-currency tax totals hidden + NCF validity display."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "justech_l10n_do_ncf 19.0.2.7.0: loaded currency/NCF validity report hotfix"
    )
