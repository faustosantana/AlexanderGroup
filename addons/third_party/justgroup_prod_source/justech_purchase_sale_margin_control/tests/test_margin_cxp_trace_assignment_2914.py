# -*- coding: utf-8 -*-
"""19.0.8.29.14 — CxP reads Trace qty.assignment as Level 5 (read-only)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCxpTraceAssignment2914(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_trace = "justech.purchase.sale.qty.assignment" in cls.env
        cls.Assign = (
            cls.env["justech.purchase.sale.qty.assignment"] if cls.has_trace else None
        )
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.Move = cls.env["account.move"]
        cls.SO = cls.env["sale.order"]
        cls.Report = cls.env["purchase.sale.payable.auxiliary.report"]

    def _skip_without_trace(self):
        if not self.has_trace:
            self.skipTest("justech.purchase.sale.qty.assignment not installed")

    def _make_product(self):
        return self.Product.create(
            {
                "name": "CxP Trace UAT Product",
                "list_price": 100,
                "standard_price": 40,
                "type": "consu",
            }
        )

    def _make_posted_bill(self, partner, product, price=80.0):
        bill = self.Move.create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-08-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.display_name,
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        self.assertFalse(
            any(
                l.purchase_line_id
                for l in bill.invoice_line_ids
                if l.display_type in (False, "product")
            )
        )
        return bill

    def _make_sale(self, partner, product, price=120.0):
        so = self.SO.create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _row_for_bill(self, bill):
        wiz = self.Report.create(
            {
                "company_ids": [(6, 0, [bill.company_id.id])],
                "date_from": bill.invoice_date,
                "date_to": bill.invoice_date,
                "situation_filter": "all",
            }
        )
        rows = [r for r in wiz._build_rows() if r["bill_id"] == bill.id]
        self.assertTrue(rows, "bill must appear in CxP open set")
        return rows[0]

    def test_01_trace_only_resolves_sale(self):
        self._skip_without_trace()
        vendor = self.Partner.create({"name": "CxP Trace Vendor", "supplier_rank": 1})
        customer = self.Partner.create({"name": "CxP Trace Customer", "customer_rank": 1})
        product = self._make_product()
        bill = self._make_posted_bill(vendor, product)
        so = self._make_sale(customer, product)
        aml = bill.invoice_line_ids[:1]
        self.Assign.create(
            {
                "company_id": bill.company_id.id,
                "vendor_bill_line_id": aml.id,
                "sale_line_id": so.order_line[:1].id,
                "quantity": 1.0,
                "amount": abs(aml.price_subtotal),
                "state": "active",
                "note": "UAT Trace-only Bill→Sale",
            }
        )
        row = self._row_for_bill(bill)
        self.assertTrue(row["has_sale"])
        self.assertIn(so.name, row["so_names"])
        self.assertEqual(row["relation_source"], "TRACE")
        self.assertEqual(row["relation_state"], "CONFIRMADA")

    def test_02_cancelled_assignment_ignored(self):
        self._skip_without_trace()
        vendor = self.Partner.create({"name": "CxP Trace Vendor2", "supplier_rank": 1})
        customer = self.Partner.create({"name": "CxP Trace Customer2", "customer_rank": 1})
        product = self._make_product()
        bill = self._make_posted_bill(vendor, product, price=55)
        so = self._make_sale(customer, product)
        self.Assign.create(
            {
                "company_id": bill.company_id.id,
                "vendor_bill_line_id": bill.invoice_line_ids[:1].id,
                "sale_line_id": so.order_line[:1].id,
                "quantity": 1.0,
                "amount": 55.0,
                "state": "cancelled",
            }
        )
        row = self._row_for_bill(bill)
        self.assertFalse(row["has_sale"])
        self.assertEqual(row["relation_source"], "SIN_RELACION")

    def test_03_unrelated_bill_stays_unresolved(self):
        vendor = self.Partner.create({"name": "CxP Orphan Vendor", "supplier_rank": 1})
        product = self._make_product()
        bill = self._make_posted_bill(vendor, product, price=33)
        row = self._row_for_bill(bill)
        self.assertFalse(row["has_sale"])
        self.assertEqual(row["so_names"], "—")
        self.assertEqual(row["relation_source"], "SIN_RELACION")
