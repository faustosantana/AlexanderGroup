# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_vendor_bill_po_control", "justech_vendor_bill_inbox")
class TestVendorBillApprovalInbox(TransactionCase):
    def test_03_approval_inbox_menu_under_vendors(self):
        menu = self.env.ref("justech_vendor_bill_po_control.menu_vendors_approval_inbox")
        self.assertEqual(menu.parent_id, self.env.ref("account.menu_finance_payables"))
        self.assertTrue(menu.action)
        self.assertTrue(menu.active)

    def test_04_obsolete_vendor_menus_inactive(self):
        my_menu = self.env.ref("justech_vendor_bill_po_control.menu_vendors_my_approvals")
        approved_menu = self.env.ref("justech_vendor_bill_po_control.menu_vendors_approved_to_post")
        self.assertFalse(my_menu.active)
        self.assertFalse(approved_menu.active)

    def test_05_inbox_action_domain_and_filters(self):
        action = self.env.ref("justech_vendor_bill_po_control.action_vendor_bills_approval_inbox")
        domain = str(action.domain or "")
        self.assertIn("pending_validation", domain)
        self.assertIn("returned", domain)
        self.assertIn("rejected", domain)
        self.assertIn("approved", domain)
        self.assertIn("search_default_pending", str(action.context or ""))

    def test_06_inbox_menus_restricted_groups(self):
        menu = self.env.ref("justech_vendor_bill_po_control.menu_vendors_approval_inbox")
        self.assertTrue(menu.group_ids, "Menú de bandeja debe restringirse por grupos")

    def test_08_vendor_bill_form_keeps_po_and_approval_buttons(self):
        view = self.env.ref("justech_vendor_bill_po_control.view_move_form_vendor_bill_po")
        arch = view.arch_db or ""
        self.assertIn("action_justech_view_related_purchase_orders", arch)
        self.assertIn("action_justech_view_approval_request", arch)
        self.assertIn("Enviar a aprobación", arch)
        self.assertNotIn("justech_margin_cxp", arch)

    def test_09_inbox_list_view_exists(self):
        view = self.env.ref("justech_vendor_bill_po_control.view_vendor_bill_approval_inbox_list")
        arch = view.arch_db or ""
        self.assertIn("vendor_bill_approver_id", arch)
        self.assertIn("vendor_bill_no_po_reason", arch)
        self.assertIn("decoration-", arch)
