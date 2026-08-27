# -*- coding: utf-8 -*-
"""Share DGII fiscal document types across companies (company_id cleared)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT COUNT(*), COUNT(company_id)
        FROM justech_do_fiscal_document_type
        """
    )
    total, with_company = cr.fetchone()
    cr.execute(
        """
        UPDATE justech_do_fiscal_document_type
           SET company_id = NULL
         WHERE company_id IS NOT NULL
        """
    )
    cleared = cr.rowcount
    _logger.info(
        "justech_l10n_do_base 19.0.1.23.0: fiscal document types total=%s "
        "with_company_before=%s cleared=%s (shared catalog)",
        total,
        with_company,
        cleared,
    )
