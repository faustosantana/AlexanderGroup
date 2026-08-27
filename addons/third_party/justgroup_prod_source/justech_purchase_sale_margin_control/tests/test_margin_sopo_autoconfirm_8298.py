# -*- coding: utf-8 -*-
"""19.0.8.29.8 — Strong SO→PO auto-confirm without Vendor Bill."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginSopoAutoconfirm8298(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "SOPO Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "SOPO Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "SOPO Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 400,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self):
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
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, origin=None):
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
                            "price_unit": 400,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

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
        if bill:
            vals["vendor_bill_ids"] = [(6, 0, [bill.id])]
        return self.Transaction.create(vals)

    def test_01_so_po_without_bill_autoconfirms(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self._mtx(so=so, po=po)
        self.assertEqual(tx._classify_trace_strength(), "STRONG_SALE_PO")
        self.assertTrue(tx._has_strong_sale_po_trace())
        self.assertFalse(tx._has_strong_sale_po_bill_trace())
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")
        stage, badge = tx._cost_document_stage()
        self.assertEqual(stage, "committed")
        self.assertIn("SIN FACTURA", badge.upper())

    def test_02_bill_keeps_validated_and_invoiced_stage(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        expense = self.env["justech.do.dgii.expense.type"].search(
            [("code", "=", "02")], limit=1
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": fields.Date.today(),
                "justech_do_expense_type_id": expense.id if expense else False,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 400,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        try:
            bill.action_post()
        except Exception:
            bill.write({"state": "posted"})
        tx = self._mtx(so=so, po=po, bill=bill, state="detected")
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")
        stage, _badge = tx._cost_document_stage()
        self.assertEqual(stage, "invoiced")

    def test_03_origin_exact_confirms_since_8299(self):
        so = self._so()
        po = self._po(origin=so.name)
        self.assertFalse(po.order_line[:1].sale_line_id)
        # Future automation on confirm already creates/validates MTX
        tx = self.Transaction.search([("sale_order_ids", "in", so.ids)], limit=1)
        if not tx:
            tx = self._mtx(so=so, po=po)
            tx.action_auto_confirm_strong_trace()
        self.assertTrue(tx._has_confirmed_sale_po_relation())
        self.assertEqual(tx.state, "validated")

    def test_04_cancelled_po_not_strong(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self._mtx(so=so, po=po)
        po.write({"state": "cancel"})
        self.assertFalse(tx._has_strong_sale_po_trace())
        confirmed = tx.action_auto_confirm_strong_trace()
        self.assertFalse(confirmed)

    def test_05_report_badge_confirmed_without_bill(self):
        so = self._so()
        po = self._po()
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self._mtx(so=so, po=po)
        tx.action_auto_confirm_strong_trace()
        Report = self.env["purchase.sale.cost.vs.sale.report"]
        st, badge = Report._relation_status_for(tx, True, True)
        self.assertEqual(st, "confirmed")
        self.assertIn("CONFIRM", badge.upper())
