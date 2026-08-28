# -*- coding: utf-8 -*-
"""Idempotent post-migrate for assigned approval (19.0.3.3.0)."""


def migrate(cr, version):
    # Ensure new columns exist even if ORM upgrade order differs (no-op if present).
    cr.execute(
        """
        ALTER TABLE account_move
            ADD COLUMN IF NOT EXISTS vendor_bill_approver_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_finance_approver_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_mgmt_approver_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_approval_deadline timestamp without time zone,
            ADD COLUMN IF NOT EXISTS vendor_bill_reassign_count integer DEFAULT 0,
            ADD COLUMN IF NOT EXISTS vendor_bill_reassign_reason text
        """
    )
    cr.execute(
        """
        ALTER TABLE res_company
            ADD COLUMN IF NOT EXISTS vendor_bill_default_finance_approver_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_default_mgmt_approver_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_default_substitute_id integer,
            ADD COLUMN IF NOT EXISTS vendor_bill_approval_deadline_hours integer DEFAULT 24,
            ADD COLUMN IF NOT EXISTS vendor_bill_notify_internal boolean DEFAULT true,
            ADD COLUMN IF NOT EXISTS vendor_bill_notify_email boolean DEFAULT true,
            ADD COLUMN IF NOT EXISTS vendor_bill_allow_reassign boolean DEFAULT true,
            ADD COLUMN IF NOT EXISTS vendor_bill_allow_admin_override boolean DEFAULT true,
            ADD COLUMN IF NOT EXISTS vendor_bill_require_sod boolean DEFAULT true
        """
    )
