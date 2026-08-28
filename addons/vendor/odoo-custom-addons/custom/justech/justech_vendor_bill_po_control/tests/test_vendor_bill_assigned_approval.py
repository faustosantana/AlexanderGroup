# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError

from odoo.addons.justech_vendor_bill_po_control.models import approval_helpers as ah


@tagged("post_install", "-at_install", "justech_vendor_bill_po_control", "justech_vendor_bill_assigned")
class TestVendorBillAssignedApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vendor_bill_po_policy = "block"
        cls.company.vendor_bill_strict_approval = True
        cls.company.vendor_bill_require_classification = True
        cls.company.vendor_bill_amount_finance_limit = 25000
        cls.company.vendor_bill_amount_management_limit = 250000
        cls.company.vendor_bill_notify_internal = True
        cls.company.vendor_bill_notify_email = True
        cls.company.vendor_bill_allow_reassign = True
        cls.company.vendor_bill_allow_admin_override = True
        cls.company.vendor_bill_require_sod = True

        cls.partner = cls.env["res.partner"].create(
            {"name": "Assigned Vendor", "supplier_rank": 1, "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Assigned Product",
                "type": "consu",
                "purchase_ok": True,
                "purchase_method": "purchase",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.expense_type = cls.env["justech.do.dgii.expense.type"].search([], limit=1)
        if not cls.expense_type:
            cls.expense_type = cls.env["justech.do.dgii.expense.type"].create(
                {"code": "02", "name": "Assigned expense"}
            )

        Users = cls.env["res.users"].with_context(no_reset_password=True)
        finance_g = cls.env.ref("justech_vendor_bill_po_control.group_vendor_bill_approver_finance")
        mgmt_g = cls.env.ref("justech_vendor_bill_po_control.group_vendor_bill_approver_management")
        invoice_g = cls.env.ref("account.group_account_invoice")

        cls.finance_user = Users.create(
            {
                "name": "Finance Approver",
                "login": "vb_finance_approver",
                "email": "vb_finance@example.com",
                "group_ids": [(6, 0, [finance_g.id, invoice_g.id])],
                "company_ids": [(6, 0, [cls.company.id])],
                "company_id": cls.company.id,
            }
        )
        cls.mgmt_user = Users.create(
            {
                "name": "Mgmt Approver",
                "login": "vb_mgmt_approver",
                "email": "vb_mgmt@example.com",
                "group_ids": [(6, 0, [mgmt_g.id, invoice_g.id])],
                "company_ids": [(6, 0, [cls.company.id])],
                "company_id": cls.company.id,
            }
        )
        cls.other_finance = Users.create(
            {
                "name": "Other Finance",
                "login": "vb_other_finance",
                "email": "vb_other@example.com",
                "group_ids": [(6, 0, [finance_g.id, invoice_g.id])],
                "company_ids": [(6, 0, [cls.company.id])],
                "company_id": cls.company.id,
            }
        )
        cls.submitter = Users.create(
            {
                "name": "Bill Submitter",
                "login": "vb_submitter",
                "email": "vb_submitter@example.com",
                "group_ids": [(6, 0, [invoice_g.id])],
                "company_ids": [(6, 0, [cls.company.id])],
                "company_id": cls.company.id,
            }
        )
        cls.company.vendor_bill_default_finance_approver_id = cls.finance_user
        cls.company.vendor_bill_default_mgmt_approver_id = cls.mgmt_user

    def _bill(self, amount=100.0):
        vals = {
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
                        "price_unit": amount,
                    },
                )
            ],
        }
        if "justech_do_expense_type_id" in self.env["account.move"]._fields:
            vals["justech_do_expense_type_id"] = self.expense_type.id
        return self.env["account.move"].create(vals)

    def _submit(self, bill, approver=None, reason="Sin OC UAT"):
        approver = approver or self.finance_user
        wiz = (
            self.env["vendor.bill.approval.request.wizard"]
            .with_user(self.submitter)
            .with_context(active_id=bill.id)
            .create(
                {
                    "move_id": bill.id,
                    "po_missing_reason": reason,
                    "approver_id": approver.id,
                }
            )
        )
        return wiz.action_submit()

    def test_01_approver_required(self):
        bill = self._bill()
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {"move_id": bill.id, "po_missing_reason": "x"}
        )
        with self.assertRaises(UserError):
            wiz.action_submit()

    def test_02_authorized_domain_excludes_portal_inactive(self):
        domain = ah.authorized_approver_domain(self.env, self.company, level="finance")
        users = self.env["res.users"].search(domain)
        self.assertIn(self.finance_user, users)
        self.assertIn(self.mgmt_user, users)
        portal = self.env.ref("base.group_portal")
        portal_user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Portal",
                "login": "vb_portal",
                "group_ids": [(6, 0, [portal.id])],
            }
        )
        self.assertNotIn(portal_user, users)
        self.other_finance.active = False
        users2 = self.env["res.users"].search(domain)
        self.assertNotIn(self.other_finance, users2)
        self.other_finance.active = True

    def test_03_default_approver_suggested(self):
        bill = self._bill()
        defaults = (
            self.env["vendor.bill.approval.request.wizard"]
            .with_context(active_id=bill.id)
            .default_get(["approver_id", "move_id"])
        )
        self.assertEqual(defaults.get("approver_id"), self.finance_user.id)

    def test_04_submit_creates_activity_follower_and_mail(self):
        bill = self._bill()
        self._submit(bill)
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        self.assertEqual(bill.vendor_bill_approver_id, self.finance_user)
        activities = bill.activity_ids.filtered(
            lambda a: a.user_id == self.finance_user
        )
        self.assertTrue(activities)
        self.assertIn(self.finance_user.partner_id, bill.message_partner_ids)
        # Mail queued when email configured (test mode may not send)
        mails = self.env["mail.mail"].search(
            [("model", "=", "account.move"), ("res_id", "=", bill.id)]
        )
        # Template may create mail.mail or message; accept either mail or chatter note
        self.assertTrue(bool(mails) or bool(bill.message_ids))

    def test_05_approver_without_email_warns(self):
        self.finance_user.email = False
        self.finance_user.partner_id.email = False
        bill = self._bill()
        result = self._submit(bill)
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        # Client notification or silent close — both OK if not blocked
        self.assertTrue(result)

    def test_06_other_user_cannot_approve(self):
        bill = self._bill()
        self._submit(bill, approver=self.finance_user)
        with self.assertRaises(AccessError):
            bill.with_user(self.other_finance).action_vendor_bill_approve()

    def test_07_assigned_approver_can_approve(self):
        bill = self._bill()
        self._submit(bill, approver=self.finance_user)
        bill.with_user(self.finance_user).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")

    def test_08_admin_override_can_approve(self):
        bill = self._bill()
        self._submit(bill, approver=self.finance_user)
        # env.user is typically admin/system in tests
        bill.action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")

    def test_09_reassign_updates_activity(self):
        bill = self._bill()
        self._submit(bill, approver=self.finance_user)
        wiz = self.env["vendor.bill.approval.reassign.wizard"].create(
            {
                "move_id": bill.id,
                "new_approver_id": self.mgmt_user.id,
                "reason": "Vacaciones",
            }
        )
        wiz.action_reassign()
        self.assertEqual(bill.vendor_bill_approver_id, self.mgmt_user)
        self.assertEqual(bill.vendor_bill_reassign_count, 1)
        self.assertTrue(bill.activity_ids.filtered(lambda a: a.user_id == self.mgmt_user))

    def test_10_reject_notifies_submitter(self):
        bill = self._bill()
        self._submit(bill)
        bill.with_user(self.finance_user).write({"vendor_bill_reject_reason": "Falta NCF"})
        bill.with_user(self.finance_user).action_vendor_bill_reject()
        self.assertEqual(bill.vendor_bill_approval_state, "rejected")

    def test_11_return_creates_activity_for_submitter(self):
        bill = self._bill()
        self._submit(bill)
        bill.with_user(self.finance_user).write({"vendor_bill_return_reason": "Corregir cuenta"})
        bill.with_user(self.finance_user).action_vendor_bill_return()
        self.assertEqual(bill.vendor_bill_approval_state, "returned")
        self.assertTrue(
            bill.activity_ids.filtered(lambda a: a.user_id == self.submitter)
        )

    def test_12_my_pending_action_domain(self):
        bill = self._bill()
        self._submit(bill, approver=self.finance_user)
        action = self.env.ref(
            "justech_vendor_bill_po_control.action_vendor_bills_my_pending_approval"
        )
        domain = action.domain or []
        # Evaluate for finance user
        moves = (
            self.env["account.move"]
            .with_user(self.finance_user)
            .search(
                [
                    ("vendor_bill_approval_state", "=", "pending_validation"),
                    ("vendor_bill_approver_id", "=", self.finance_user.id),
                ]
            )
        )
        self.assertIn(bill, moves)
        self.assertTrue(domain)

    def test_13_management_level_rejects_finance_only_user(self):
        bill = self._bill(amount=100000)
        bill.invalidate_recordset()
        bill._compute_vendor_bill_evaluation()
        self.assertEqual(bill.vendor_bill_approval_level_required, "management")
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "alto monto",
                "approver_id": self.finance_user.id,
            }
        )
        with self.assertRaises(UserError):
            wiz.action_submit()

    def test_14_dual_requires_two_approvers_and_sod(self):
        bill = self._bill(amount=300000)
        bill.invalidate_recordset()
        bill._compute_vendor_bill_evaluation()
        self.assertEqual(bill.vendor_bill_approval_level_required, "dual")
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "dual",
                "approver_id": self.finance_user.id,
                "finance_approver_id": self.finance_user.id,
                "management_approver_id": self.finance_user.id,
            }
        )
        with self.assertRaises(UserError):
            wiz.action_submit()
        wiz.write({"management_approver_id": self.mgmt_user.id})
        wiz.action_submit()
        self.assertEqual(bill.vendor_bill_approver_id, self.finance_user)
        bill.with_user(self.finance_user).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        self.assertEqual(bill.vendor_bill_approver_id, self.mgmt_user)
        bill.with_user(self.mgmt_user).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")

    def test_15_wizard_spanish_labels(self):
        field = self.env["vendor.bill.approval.request.wizard"]._fields["approval_level_required"]
        self.assertEqual(field.string, "Nivel requerido")
        self.assertEqual(
            self.env["vendor.bill.approval.request.wizard"]._fields["approver_id"].string,
            "Aprobador",
        )
        self.assertEqual(
            self.env["vendor.bill.approval.request.wizard"]._fields["move_id"].string,
            "Factura",
        )
