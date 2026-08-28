# -*- coding: utf-8 -*-
"""Mark already-posted vendor bills as legacy_approved; leave drafts for evaluation."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move
           SET vendor_bill_approval_state = 'legacy_approved'
         WHERE move_type IN ('in_invoice', 'in_refund')
           AND state = 'posted'
           AND (vendor_bill_approval_state IS NULL
                OR vendor_bill_approval_state IN ('draft', ''))
        """
    )
    cr.execute(
        """
        UPDATE account_move
           SET vendor_bill_approval_state = 'draft'
         WHERE move_type IN ('in_invoice', 'in_refund')
           AND state = 'draft'
           AND vendor_bill_approval_state IS NULL
        """
    )
