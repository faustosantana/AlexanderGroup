# -*- coding: utf-8 -*-
"""19.0.8.29.7 — Strong SO→PO→Bill auto-confirm (no heuristics)."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginStrongTraceAutoconfirm8297(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "ST Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "ST Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "ST Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 400,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self, price=1000):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, price=400, origin=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "origin": origin or False,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _bill(self, po, price=None, post=True, qty=1.0):
        expense = self.env["justech.do.dgii.expense.type"].search(
            [("code", "=", "02")], limit=1
        )
        vals = {
            "move_type": "in_invoice",
            "partner_id": po.partner_id.id,
            "company_id": self.company.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "quantity": qty,
                        "price_unit": price
                        if price is not None
                        else po.order_line[:1].price_unit,
                        "purchase_line_id": po.order_line[:1].id,
                        "name": self.product.name,
                    },
                )
            ],
        }
        if expense:
            vals["justech_do_expense_type_id"] = expense.id
        bill = self.env["account.move"].create(vals)
        if post:
            try:
                bill.action_post()
            except Exception:
                # Fiscal/NCF may block in stripped test DBs; force posted for FK tests only.
                bill.write({"state": "posted"})
        return bill

    def _mtx(self, so=None, po=None, bill=None, state="detected"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": "2026-06-20",
            "state": state,
            "validation_state": "pending",
            "source": "backfill",
            "is_uat_fixture": True,
        }
        if so:
            vals["customer_id"] = so.partner_id.id
            vals["sale_order_ids"] = [(6, 0, [so.id])]
            vals["name"] = so.name
        if po:
            vals["purchase_order_ids"] = [(6, 0, [po.id])]
            vals["supplier_ids"] = [(6, 0, [po.partner_id.id])]
        if bill:
            vals["vendor_bill_ids"] = [(6, 0, [bill.id])]
        return self.Transaction.create(vals)

    def test_01_strong_so_po_bill_autoconfirms(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po)
        tx = self._mtx(so=so, po=po, bill=bill, state="detected")
        self.assertEqual(tx._classify_trace_strength(), "STRONG_CONFIRMED")
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertEqual(confirmed, tx)
        self.assertEqual(tx.state, "validated")
        self.assertEqual(tx.validation_state, "validated")

    def test_02_multi_po_multi_bill_autoconfirms(self):
        so = self._so(price=2000)
        po1 = self._po(price=400)
        po2 = self._po(price=500)
        po1.order_line[:1].sale_line_id = so.order_line[:1]
        po2.order_line[:1].sale_line_id = so.order_line[:1]
        b1 = self._bill(po1, price=400)
        b2 = self._bill(po2, price=500)
        tx = self._mtx(so=so, po=None, bill=None)
        tx.write(
            {
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
                "vendor_bill_ids": [(6, 0, [b1.id, b2.id])],
            }
        )
        self.assertTrue(tx._has_strong_sale_po_bill_trace())
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")

    def test_03_partial_bill_still_strong(self):
        so = self._so()
        po = self._po(price=400)
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po, price=400, qty=0.5)
        tx = self._mtx(so=so, po=po, bill=bill)
        self.assertEqual(tx._classify_trace_strength(), "STRONG_CONFIRMED")
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")

    def test_04_origin_exact_autoconfirms_since_8299(self):
        """29.9: origin exact (same company) confirms without sale_line_id."""
        so = self._so()
        po = self._po(origin=so.name)
        self.assertFalse(po.order_line[:1].sale_line_id)
        bill = self._bill(po)
        tx = self.Transaction.search([("sale_order_ids", "in", so.ids)], limit=1)
        if not tx:
            tx = self._mtx(so=so, po=po, bill=bill)
        else:
            tx.write({"vendor_bill_ids": [(4, bill.id)]})
        self.assertIn(tx._classify_trace_strength(), ("ORIGIN_EXACT", "STRONG_CONFIRMED"))
        if tx.state not in ("validated", "approved", "closed"):
            tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")

    def test_05_sale_po_without_bill_autoconfirms_since_8298(self):
        """29.8: strong SO→PO alone is enough for relation confirmation."""
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self._mtx(so=so, po=po, bill=None)
        self.assertEqual(tx._classify_trace_strength(), "STRONG_SALE_PO")
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertEqual(confirmed, tx)
        self.assertEqual(tx.state, "validated")

    def test_06_po_bill_without_sale_unrelated(self):
        po = self._po()
        bill = self._bill(po)
        tx = self._mtx(so=None, po=po, bill=bill)
        self.assertEqual(tx._classify_trace_strength(), "STRONG_PO_BILL")
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertFalse(confirmed)

    def test_07_cancelled_po_not_strong(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po)
        tx = self._mtx(so=so, po=po, bill=bill)
        # Force cancel flag (button_cancel may be blocked by posted bill)
        po.write({"state": "cancel"})
        self.assertFalse(tx._has_strong_sale_po_bill_trace())
        self.assertFalse(tx._has_strong_sale_po_trace())
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertFalse(confirmed)

    def test_08_cancelled_bill_so_po_still_confirms(self):
        """Bill cancel does not undo SO→PO relation strength (29.8)."""
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po, post=False)
        tx = self._mtx(so=so, po=po, bill=bill)
        self.assertFalse(tx._has_strong_sale_po_bill_trace())
        bill.write({"state": "cancel"})
        self.assertFalse(tx._has_strong_sale_po_bill_trace())
        self.assertTrue(tx._has_strong_sale_po_trace())
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertEqual(confirmed, tx)
        self.assertEqual(tx.state, "validated")

    def test_09_report_badge_confirmed_after_validate(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po)
        tx = self._mtx(so=so, po=po, bill=bill)
        tx.action_auto_confirm_strong_trace()
        Report = self.env["purchase.sale.cost.vs.sale.report"]
        st, badge = Report._relation_status_for(tx, True, True)
        self.assertEqual(st, "confirmed")
        self.assertIn("CONFIRM", badge.upper())

    def test_10_idempotent_second_call(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        bill = self._bill(po)
        tx = self._mtx(so=so, po=po, bill=bill)
        tx.action_auto_confirm_strong_trace()
        again = tx.action_auto_confirm_strong_trace()
        self.assertFalse(again)
        self.assertEqual(tx.state, "validated")
