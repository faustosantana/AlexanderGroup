# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged(
    "post_install",
    "-at_install",
    "justech_vendor_bill_po_control",
    "justech_vendor_bill_legacy_security",
)
class TestVendorBillLegacyAndApproveSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vendor_bill_po_policy = "block"
        cls.company.vendor_bill_strict_approval = True
        cls.company.vendor_bill_allow_self_approval = False
        cls.company.vendor_bill_allow_admin_override = True
        # Policy applies only after effective_from (forward-only).
        cls.company.vendor_bill_approval_effective_from = fields.Datetime.now() - timedelta(
            minutes=5
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Legacy Sec Vendor", "supplier_rank": 1, "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Legacy Sec Product",
                "type": "consu",
                "purchase_ok": True,
                "purchase_method": "purchase",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        finance_g = cls.env.ref("justech_vendor_bill_po_control.group_vendor_bill_approver_finance")
        invoice_g = cls.env.ref("account.group_account_invoice")
        purchase_g = cls.env.ref("purchase.group_purchase_user")
        mgr_g = cls.env.ref("account.group_account_manager")
        cls.approver = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Legacy Finance Approver",
                    "login": "vb_legacy_fin",
                    "email": "vb_legacy_fin@example.com",
                    "group_ids": [(6, 0, [finance_g.id, invoice_g.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.ap_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Legacy AP User",
                    "login": "vb_legacy_ap",
                    "email": "vb_legacy_ap@example.com",
                    "group_ids": [(6, 0, [invoice_g.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.purchase_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Legacy Purchase User",
                    "login": "vb_legacy_po",
                    "email": "vb_legacy_po@example.com",
                    "group_ids": [(6, 0, [purchase_g.id, invoice_g.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.account_mgr = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Legacy Account Manager",
                    "login": "vb_legacy_am",
                    "email": "vb_legacy_am@example.com",
                    "group_ids": [(6, 0, [mgr_g.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.company.vendor_bill_default_finance_approver_id = cls.approver

    def _bill(self, create_date=None):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        if create_date:
            self.env.cr.execute(
                "UPDATE account_move SET create_date = %s WHERE id = %s",
                [create_date, move.id],
            )
            move.invalidate_recordset()
        move._compute_vendor_bill_legacy_exempt()
        move._compute_vendor_bill_button_flags()
        return move

    def test_legacy_exempt_before_effective_keeps_confirm(self):
        past_dt = fields.Datetime.now() - timedelta(days=30)
        bill = self._bill(create_date=past_dt)
        self.assertTrue(bill.vendor_bill_legacy_exempt)
        self.assertFalse(bill._justech_strict_enabled())
        self.assertTrue(bill.vendor_bill_show_confirm)

    def test_new_bill_without_po_hides_confirm(self):
        bill = self._bill()
        self.assertFalse(bill.vendor_bill_legacy_exempt)
        self.assertTrue(bill._justech_strict_enabled())
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertTrue(bill.vendor_bill_show_submit_validation)

    def test_ap_user_cannot_approve_rpc(self):
        bill = self._bill()
        bill.with_user(self.approver)._justech_wf_write(
            {
                "vendor_bill_approval_state": "pending_validation",
                "vendor_bill_submitted_by": self.ap_user.id,
                "vendor_bill_approver_id": self.approver.id,
                "vendor_bill_no_po_reason": "UAT",
            }
        )
        with self.assertRaises(AccessError):
            bill.with_user(self.ap_user).action_vendor_bill_approve()

    def test_purchase_user_cannot_approve_rpc(self):
        bill = self._bill()
        bill._justech_wf_write(
            {
                "vendor_bill_approval_state": "pending_validation",
                "vendor_bill_submitted_by": self.purchase_user.id,
                "vendor_bill_approver_id": self.approver.id,
                "vendor_bill_no_po_reason": "UAT",
            }
        )
        with self.assertRaises(AccessError):
            bill.with_user(self.purchase_user).action_vendor_bill_approve()

    def test_finance_approver_can_approve(self):
        bill = self._bill()
        bill._justech_wf_write(
            {
                "vendor_bill_approval_state": "pending_validation",
                "vendor_bill_submitted_by": self.ap_user.id,
                "vendor_bill_approver_id": self.approver.id,
                "vendor_bill_no_po_reason": "UAT",
                "vendor_bill_approval_level_required": "finance",
            }
        )
        bill.with_user(self.approver).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")

    def test_account_manager_can_approve(self):
        bill = self._bill()
        bill._justech_wf_write(
            {
                "vendor_bill_approval_state": "pending_validation",
                "vendor_bill_submitted_by": self.ap_user.id,
                "vendor_bill_approver_id": self.account_mgr.id,
                "vendor_bill_no_po_reason": "UAT",
                "vendor_bill_approval_level_required": "finance",
            }
        )
        bill.with_user(self.account_mgr).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")

    def test_self_approval_blocked_for_finance(self):
        bill = self._bill()
        bill._justech_wf_write(
            {
                "vendor_bill_approval_state": "pending_validation",
                "vendor_bill_submitted_by": self.approver.id,
                "vendor_bill_approver_id": self.approver.id,
                "vendor_bill_no_po_reason": "UAT",
                "vendor_bill_approval_level_required": "finance",
            }
        )
        with self.assertRaises(AccessError):
            bill.with_user(self.approver).action_vendor_bill_approve()
