# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


@tagged("post_install", "-at_install", "justech_vendor_bill_po_control")
class TestVendorBillPoControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Legacy PO-policy tests must not run under strict approval.
        cls.company.vendor_bill_strict_approval = False
        cls.partner = cls.env["res.partner"].create(
            {"name": "UAT Vendor PO Control", "supplier_rank": 1, "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "UAT PO Product",
                "type": "consu",
                "purchase_ok": True,
                "purchase_method": "purchase",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.journal:
            raise AssertionError("Se requiere diario purchase")

    def _bill(self, with_po=False):
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
                            "name": "UAT line",
                            "quantity": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        if with_po:
            po = self.env["purchase.order"].create(
                {
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "name": "PO line",
                                "product_qty": 1,
                                "price_unit": 100,
                            },
                        )
                    ],
                }
            )
            po.button_confirm()
            move.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
            move.invalidate_recordset()
            move._compute_related_purchase_orders()
        return move

    def test_policy_disabled_allows_post_without_po(self):
        self.company.vendor_bill_po_policy = "disabled"
        bill = self._bill(with_po=False)
        # No raise from PO control (fiscal 606/NCF is out of scope for this unit).
        bill._justech_check_vendor_bill_po_requirement()
        self.assertEqual(bill.state, "draft")

    def test_policy_warning_allows_post_without_po(self):
        self.company.vendor_bill_po_policy = "warning"
        bill = self._bill(with_po=False)
        bill._justech_check_vendor_bill_po_requirement()
        self.assertEqual(bill.state, "draft")

    def test_policy_block_raises_without_po(self):
        self.company.vendor_bill_po_policy = "block"
        bill = self._bill(with_po=False)
        with self.assertRaises(UserError):
            bill._justech_check_vendor_bill_po_requirement()
        self.assertEqual(bill.state, "draft")

    def test_policy_block_allows_with_po(self):
        self.company.vendor_bill_po_policy = "block"
        bill = self._bill(with_po=True)
        self.assertTrue(bill.has_valid_purchase_order)
        bill._justech_check_vendor_bill_po_requirement()

    def test_manual_exception_requires_approval(self):
        self.company.vendor_bill_po_policy = "block"
        bill = self._bill(with_po=False)
        bill.po_exception_reason = "Gasto administrativo UAT"
        bill.action_justech_approve_po_exception()
        self.assertTrue(bill.po_requirement_exception)
        self.assertTrue(bill.po_exception_approved_by)
        bill._justech_check_vendor_bill_po_requirement()

    def test_exception_without_approval_still_blocks(self):
        self.company.vendor_bill_po_policy = "block"
        self.company.vendor_bill_strict_approval = False
        bill = self._bill(with_po=False)
        bill.with_context(justech_vendor_bill_workflow=True).write(
            {
                "po_requirement_exception": True,
                "po_exception_reason": "Sin aprobación",
            }
        )
        with self.assertRaises(UserError):
            bill._justech_check_vendor_bill_po_requirement()

    def test_cancelled_po_not_valid(self):
        self.company.vendor_bill_po_policy = "block"
        bill = self._bill(with_po=True)
        po = bill.related_purchase_order_ids
        po.button_cancel()
        bill.invalidate_recordset()
        bill._compute_related_purchase_orders()
        self.assertFalse(bill.has_valid_purchase_order)
        with self.assertRaises(UserError):
            bill._justech_check_vendor_bill_po_requirement()

    def test_customer_invoice_not_affected(self):
        self.company.vendor_bill_po_policy = "block"
        move = self.env["account.move"].new(
            {"move_type": "out_invoice", "company_id": self.company.id}
        )
        move._justech_check_vendor_bill_po_requirement()

    def test_vendor_refund_with_origin_not_blocked(self):
        self.company.vendor_bill_po_policy = "block"
        origin = self._bill(with_po=False)
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "reversed_entry_id": origin.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "UAT refund",
                            "quantity": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        refund._justech_check_vendor_bill_po_requirement()

    def test_multi_po_count(self):
        bill = self._bill(with_po=True)
        po2 = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "PO2",
                            "product_qty": 1,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )
        po2.button_confirm()
        self.env["account.move.line"].create(
            {
                "move_id": bill.id,
                "product_id": self.product.id,
                "name": "second line",
                "quantity": 1,
                "price_unit": 50,
                "purchase_line_id": po2.order_line[0].id,
            }
        )
        bill.invalidate_recordset()
        bill._compute_related_purchase_orders()
        self.assertGreaterEqual(bill.related_purchase_order_count, 2)
