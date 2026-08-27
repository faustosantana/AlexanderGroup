# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginControl(TransactionCase):
    """Self-contained coverage of the audit approved rules for
    justech_purchase_sale_margin_control. No dependency on
    bi_convert_purchase_from_sales: purchase<->sale traceability is simulated
    directly via purchase.order.line.sale_line_id and purchase.order.origin.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Margin Test Co B"})

        cls.customer = cls.env["res.partner"].create(
            {"name": "Margin Test Customer", "company_id": False}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Margin Test Vendor", "company_id": False}
        )

        cls.product_stock = cls.env["product.product"].create(
            {
                "name": "Margin Test Stockable Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 150.0,
                "standard_price": 80.0,
            }
        )
        cls.product_service = cls.env["product.product"].create(
            {
                "name": "Margin Test Admin Service",
                "type": "service",
                "list_price": 50.0,
                "standard_price": 30.0,
            }
        )

        cls.trace_engine = cls.env["purchase.sale.trace.engine"]
        cls.margin_service = cls.env["purchase.sale.margin.service"]
        cls.classification_service = cls.env["purchase.sale.classification.service"]
        cls.Allocation = cls.env["purchase.sale.cost.allocation"]
        cls.Link = cls.env["purchase.sale.cost.link"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_sale_order(self, product, qty=1.0, price=100.0, taxes=None, company=None):
        company = company or self.company
        line_vals = {
            "product_id": product.id,
            "name": product.name,
            "product_uom_qty": qty,
            "price_unit": price,
        }
        if taxes is not None:
            line_vals["tax_ids"] = [(6, 0, taxes.ids)]
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "company_id": company.id,
                "order_line": [(0, 0, line_vals)],
            }
        )

    def _create_purchase_order(self, product, qty=1.0, price=60.0, company=None, origin=False):
        company = company or self.company
        vals = {
            "partner_id": self.vendor.id,
            "company_id": company.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "product_qty": qty,
                        "price_unit": price,
                    },
                )
            ],
        }
        if origin:
            vals["origin"] = origin
        return self.env["purchase.order"].create(vals)

    def _create_vendor_bill(
        self, product, purchase_line=False, qty=1.0, price=60.0, move_type="in_invoice", company=None
    ):
        company = company or self.company
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.vendor.id,
                "company_id": company.id,
                "invoice_date": date(2026, 3, 1),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": qty,
                            "price_unit": price,
                            "purchase_line_id": purchase_line.id if purchase_line else False,
                        },
                    )
                ],
            }
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def test_classification_defaults_to_inventory_pending(self):
        """Rule: a purchase.order.line defaults to inventory_pending, never
        administrative_expense, before any classification runs."""
        po = self._create_purchase_order(self.product_stock)
        line = po.order_line[0]
        self.assertEqual(line.cost_usage_type, "inventory_pending")

    def test_classification_stock_without_sale_is_inventory_pending(self):
        """Rule: stock purchased with no linked sale = inventory_pending,
        never administrative_expense."""
        po = self._create_purchase_order(self.product_stock)
        line = po.order_line[0]
        usage_type, confidence, _reason = self.classification_service.suggest_cost_usage_type(line)
        self.assertEqual(usage_type, "inventory_pending")
        self.assertNotEqual(usage_type, "administrative_expense")
        self.assertGreater(confidence, 0)

    def test_classification_service_without_sale_is_admin_expense(self):
        po = self._create_purchase_order(self.product_service)
        line = po.order_line[0]
        usage_type, _confidence, _reason = self.classification_service.suggest_cost_usage_type(line)
        self.assertEqual(usage_type, "administrative_expense")

    def test_action_suggest_classification_respects_manual_flag(self):
        po = self._create_purchase_order(self.product_service)
        line = po.order_line[0]
        line.write({"cost_usage_type": "asset"})  # manual edit -> classification_is_manual=True
        self.assertTrue(line.classification_is_manual)
        line.action_suggest_classification()
        # manual classification must not be overwritten by the suggestion engine
        self.assertEqual(line.cost_usage_type, "asset")

    # ------------------------------------------------------------------
    # Multi-company / allocation integrity
    # ------------------------------------------------------------------
    def test_allocation_same_company_constraint(self):
        """Rule: no cross-company allocations."""
        so_other = self._create_sale_order(self.product_stock, company=self.other_company)
        with self.assertRaises(ValidationError):
            self.Allocation.create(
                {
                    "company_id": self.company.id,
                    "sale_order_id": so_other.id,
                    "allocated_amount": 10.0,
                    "currency_id": self.company.currency_id.id,
                }
            )

    def test_over_allocation_blocked(self):
        """Rule: allocations may never exceed the available source amount."""
        po = self._create_purchase_order(self.product_stock, qty=1, price=100.0)
        line = po.order_line[0]
        bill = self._create_vendor_bill(self.product_stock, purchase_line=line, qty=1, price=100.0)
        bill_line = bill.invoice_line_ids[0]

        self.Allocation.create(
            {
                "company_id": self.company.id,
                "vendor_bill_id": bill.id,
                "vendor_bill_line_id": bill_line.id,
                "purchase_order_id": po.id,
                "purchase_order_line_id": line.id,
                "allocated_amount": 60.0,
                "currency_id": self.company.currency_id.id,
                "state": "confirmed",
            }
        )
        with self.assertRaises(ValidationError):
            self.Allocation.create(
                {
                    "company_id": self.company.id,
                    "vendor_bill_id": bill.id,
                    "vendor_bill_line_id": bill_line.id,
                    "purchase_order_id": po.id,
                    "purchase_order_line_id": line.id,
                    "allocated_amount": 60.0,
                    "currency_id": self.company.currency_id.id,
                    "state": "confirmed",
                }
            )

    def test_credit_note_negative_amount_allowed(self):
        """Rule: negative allocated_amount only allowed against a refund."""
        refund = self._create_vendor_bill(self.product_stock, qty=1, price=50.0, move_type="in_refund")
        refund_line = refund.invoice_line_ids[0]
        allocation = self.Allocation.create(
            {
                "company_id": self.company.id,
                "vendor_bill_id": refund.id,
                "vendor_bill_line_id": refund_line.id,
                "allocated_amount": -50.0,
                "currency_id": self.company.currency_id.id,
                "state": "confirmed",
            }
        )
        self.assertTrue(allocation)
        self.assertEqual(allocation.allocated_amount, -50.0)

        normal_bill = self._create_vendor_bill(self.product_stock, qty=1, price=100.0, move_type="in_invoice")
        with self.assertRaises(ValidationError):
            self.Allocation.create(
                {
                    "company_id": self.company.id,
                    "vendor_bill_id": normal_bill.id,
                    "vendor_bill_line_id": normal_bill.invoice_line_ids[0].id,
                    "allocated_amount": -50.0,
                    "currency_id": self.company.currency_id.id,
                    "state": "confirmed",
                }
            )

    # ------------------------------------------------------------------
    # Trace engine / manual lock
    # ------------------------------------------------------------------
    def test_manual_confirmed_link_not_overwritten_by_recompute(self):
        """Rule: never overwrite confirmed manual allocations/links."""
        so1 = self._create_sale_order(self.product_stock)
        so2 = self._create_sale_order(self.product_stock)
        po = self._create_purchase_order(self.product_stock)
        line = po.order_line[0]

        link = self.Link.create(
            {
                "company_id": self.company.id,
                "purchase_id": po.id,
                "purchase_line_id": line.id,
                "sale_id": so1.id,
                "is_manual": True,
                "state": "confirmed",
                "link_source": "manual",
                "confidence": 100,
            }
        )

        # Simulate a different, higher-priority automatic trace target appearing later.
        line.sale_line_id = so2.order_line[0].id

        changed = self.trace_engine.recompute_link(link)

        self.assertFalse(changed)
        self.assertEqual(link.sale_id.id, so1.id)
        self.assertEqual(link.state, "confirmed")

    def test_trace_engine_purchase_line_bridge_confidence_100(self):
        so = self._create_sale_order(self.product_stock)
        po = self._create_purchase_order(self.product_stock)
        line = po.order_line[0]
        line.sale_line_id = so.order_line[0].id

        match = self.trace_engine.find_best_match(purchase_line=line)
        self.assertIsNotNone(match)
        self.assertEqual(match["source"], "purchase_line")
        self.assertEqual(match["confidence"], 100)
        self.assertFalse(match["ambiguous"])

    def test_trace_engine_origin_never_reaches_100(self):
        """Rule: origin alone must never grant 100% confidence."""
        so = self._create_sale_order(self.product_stock)
        po = self._create_purchase_order(self.product_stock, origin=so.name)
        line = po.order_line[0]

        match = self.trace_engine.find_best_match(purchase_line=line)
        self.assertIsNotNone(match)
        self.assertEqual(match["source"], "origin")
        self.assertLess(match["confidence"], 100)

    # ------------------------------------------------------------------
    # Margin formula (no tax in base)
    # ------------------------------------------------------------------
    def test_margin_formula_excludes_tax(self):
        tax = self.env["account.tax"].create(
            {
                "name": "Margin Test ITBIS 18%",
                "amount": 18.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0, taxes=tax)
        self.assertAlmostEqual(so.amount_untaxed, 100.0, places=2)
        self.assertGreater(so.amount_total, so.amount_untaxed)

        self.Allocation.create(
            {
                "company_id": self.company.id,
                "sale_order_id": so.id,
                "allocated_amount": 40.0,
                "currency_id": self.company.currency_id.id,
                "cost_usage_type": "resale_direct",
                "state": "confirmed",
            }
        )

        data = self.margin_service.compute_for_sale_order(so)
        self.assertAlmostEqual(data["revenue"], 100.0, places=2)
        self.assertAlmostEqual(data["real_cost"], 40.0, places=2)
        self.assertAlmostEqual(data["real_margin"], 60.0, places=2)
        self.assertAlmostEqual(data["real_margin_pct"], 60.0, places=2)

    def test_admin_expense_excluded_from_margin(self):
        """Rule: administrative_expense allocations never dent the sales margin."""
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0)
        self.Allocation.create(
            {
                "company_id": self.company.id,
                "sale_order_id": so.id,
                "allocated_amount": 20.0,
                "currency_id": self.company.currency_id.id,
                "cost_usage_type": "administrative_expense",
                "state": "confirmed",
            }
        )
        data = self.margin_service.compute_for_sale_order(so)
        self.assertAlmostEqual(data["real_cost"], 0.0, places=2)
        self.assertAlmostEqual(data["real_margin"], 100.0, places=2)

    # ------------------------------------------------------------------
    # Backfill (2026 only, dry-run first)
    # ------------------------------------------------------------------
    def test_backfill_dry_run_creates_nothing(self):
        # `fields.Datetime.now()` defaults purchase.order.date_order to the
        # current date, which falls within year 2026 for this test suite.
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0)
        po = self._create_purchase_order(self.product_stock, qty=1, price=60.0)
        line = po.order_line[0]
        line.sale_line_id = so.order_line[0].id
        po.button_confirm()
        self.assertEqual(po.date_order.year, 2026)

        link_count_before = self.Link.search_count([])
        alloc_count_before = self.Allocation.search_count([])

        wizard = self.env["purchase.sale.backfill.wizard"].create(
            {
                "year": 2026,
                "company_ids": [(6, 0, [self.company.id])],
                "dry_run": True,
            }
        )
        wizard.action_run()

        link_count_after = self.Link.search_count([])
        alloc_count_after = self.Allocation.search_count([])

        self.assertEqual(link_count_before, link_count_after)
        self.assertEqual(alloc_count_before, alloc_count_after)
        self.assertEqual(wizard.state, "done")
        self.assertGreaterEqual(wizard.scanned_po_lines, 1)
        self.assertGreaterEqual(wizard.links_created, 1)

    def test_backfill_year_restricted_to_2026(self):
        with self.assertRaises(ValidationError):
            self.env["purchase.sale.backfill.wizard"].create({"year": 2025})
