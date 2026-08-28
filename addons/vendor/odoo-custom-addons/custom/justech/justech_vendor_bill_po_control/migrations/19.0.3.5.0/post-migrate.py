# -*- coding: utf-8 -*-
"""Idempotent post-migrate for UX final auto-post (19.0.3.5.0)."""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE res_company
            ADD COLUMN IF NOT EXISTS vendor_bill_no_po_auto_classification varchar
        """
    )
    # Ensure 'direct' is allowed in classification; no rewrite of posted moves.
    return
