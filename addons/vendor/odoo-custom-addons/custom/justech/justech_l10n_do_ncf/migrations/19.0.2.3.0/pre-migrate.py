# -*- coding: utf-8 -*-
"""Align DB unique indexes with NCF duplicate rule v2.0 (sales vs purchases).

Rollback: see evidence/enterprise-audit-remediation/rollback/ncf_unique_idx.sql
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY = "account_move_justech_do_ncf_company_uniq"
SALE = "account_move_justech_do_ncf_sale_uniq"
PURCHASE = "account_move_justech_do_ncf_purchase_uniq"


def migrate(cr, version):
    # Pre-check: incompatible duplicates under NEW rules must stop migration.
    cr.execute(
        """
        SELECT company_id, justech_do_ncf, COUNT(*)
        FROM account_move
        WHERE state = 'posted'
          AND COALESCE(justech_do_ncf, '') <> ''
          AND COALESCE(justech_do_ncf_voided, false) = false
          AND move_type IN ('out_invoice', 'out_refund', 'out_receipt')
        GROUP BY company_id, justech_do_ncf
        HAVING COUNT(*) > 1
        LIMIT 5
        """
    )
    sale_dups = cr.fetchall()
    cr.execute(
        """
        SELECT company_id, partner_id, justech_do_ncf, COUNT(*)
        FROM account_move
        WHERE state = 'posted'
          AND COALESCE(justech_do_ncf, '') <> ''
          AND COALESCE(justech_do_ncf_voided, false) = false
          AND move_type IN ('in_invoice', 'in_refund', 'in_receipt')
        GROUP BY company_id, partner_id, justech_do_ncf
        HAVING COUNT(*) > 1
        LIMIT 5
        """
    )
    purchase_dups = cr.fetchall()
    if sale_dups or purchase_dups:
        raise Exception(
            "NCF-UNIQUE-IDX migration aborted: incompatible duplicates exist. "
            "sale=%s purchase=%s" % (sale_dups, purchase_dups)
        )

    cr.execute(f"DROP INDEX IF EXISTS {LEGACY}")
    cr.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {SALE}
        ON account_move (company_id, justech_do_ncf)
        WHERE state = 'posted'
          AND justech_do_ncf IS NOT NULL
          AND justech_do_ncf != ''
          AND COALESCE(justech_do_ncf_voided, false) = false
          AND move_type IN ('out_invoice', 'out_refund', 'out_receipt')
        """
    )
    cr.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {PURCHASE}
        ON account_move (company_id, partner_id, justech_do_ncf)
        WHERE state = 'posted'
          AND justech_do_ncf IS NOT NULL
          AND justech_do_ncf != ''
          AND COALESCE(justech_do_ncf_voided, false) = false
          AND move_type IN ('in_invoice', 'in_refund', 'in_receipt')
        """
    )
    _logger.info(
        "justech_l10n_do_ncf: replaced %s with %s + %s", LEGACY, SALE, PURCHASE
    )
