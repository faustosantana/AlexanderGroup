# -*- coding: utf-8 -*-
"""Idempotent migration for final PO flow: keep historical posted bills intact."""


def migrate(cr, version):
    if not version:
        return
    # Ensure obsolete classification is not required; no data rewrite of posted moves.
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'account_move' AND column_name = 'vendor_bill_classification'
        """
    )
    if not cr.fetchone():
        return
    # No-op data change: documentation marker only.
    cr.execute(
        """
        SELECT COUNT(*) FROM account_move
        WHERE move_type IN ('in_invoice', 'in_refund', 'in_receipt')
          AND state = 'posted'
          AND vendor_bill_approval_state = 'legacy_approved'
        """
    )
    # Intentionally do not UPDATE posted historical rows.
