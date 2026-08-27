# -*- coding: utf-8 -*-
"""Keep historical approval data; no accounting changes."""


def migrate(cr, version):
    if not version:
        return
    # Ensure legacy reasons remain readable via smart button (no rewrite of posted moves).
    cr.execute(
        """
        SELECT COUNT(*) FROM account_move
        WHERE move_type IN ('in_invoice', 'in_refund', 'in_receipt')
          AND (
            vendor_bill_no_po_reason IS NOT NULL
            OR vendor_bill_submitted_by IS NOT NULL
            OR vendor_bill_approval_state NOT IN ('draft')
          )
        """
    )
