# -*- coding: utf-8 -*-
"""Idempotent forward-only stamp. No backfill of approval, payments, or journals."""


def migrate(cr, version):
    # Column may already exist from ORM update; set only when NULL.
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'res_company'
           AND column_name = 'vendor_bill_approval_effective_from'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_company
           SET vendor_bill_approval_effective_from =
               COALESCE(vendor_bill_approval_effective_from, (now() AT TIME ZONE 'utc'))
         WHERE vendor_bill_approval_effective_from IS NULL
        """
    )
    # Explicitly do NOT:
    # - update account_move approval states
    # - create activities
    # - alter payments / reconciliations / NCF / taxes / amounts
