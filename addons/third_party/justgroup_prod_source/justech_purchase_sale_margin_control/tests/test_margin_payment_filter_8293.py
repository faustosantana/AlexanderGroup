# -*- coding: utf-8 -*-
"""19.0.8.29.3 — Cost vs Sales vendor payment filter uses residual + cost-only ops."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.payable_cxp_source import open_vendor_bill_domain


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginPaymentFilter8293(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.company = cls.env.company

    def _report(self, **vals):
        defaults = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "show_complete": True,
            "show_incomplete": False,
            "show_sales_without_cost": False,
            "show_costs_without_sale": False,
            "vendor_payment_state": "all",
            "customer_payment_state": "all",
            "vendor_doc_type": "all",
        }
        defaults.update(vals)
        return self.Report.create(defaults)

    def test_01_pending_uses_residual_not_exact_state(self):
        r = self._report()
        pending = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill_id": 1,
                "bill": "B1",
                "total": 100.0,
                "residual": 40.0,
                "raw_payment_state": "partial",
            }
        )
        self.assertTrue(r._cost_matches_vendor_payment(pending, "not_paid"))
        paid = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill_id": 2,
                "bill": "B2",
                "total": 100.0,
                "residual": 0.0,
                "raw_payment_state": "paid",
            }
        )
        self.assertFalse(r._cost_matches_vendor_payment(paid, "not_paid"))
        self.assertTrue(r._cost_matches_vendor_payment(paid, "paid"))

    def test_02_multiple_bills_any_open_is_pending_once(self):
        r = self._report()
        costs = [
            r._decorate_cost_payment(
                {
                    "kind": "bill",
                    "bill_id": 1,
                    "bill": "PAID",
                    "total": 50.0,
                    "residual": 0.0,
                    "raw_payment_state": "paid",
                }
            ),
            r._decorate_cost_payment(
                {
                    "kind": "bill",
                    "bill_id": 2,
                    "bill": "OPEN",
                    "total": 80.0,
                    "residual": 80.0,
                    "raw_payment_state": "not_paid",
                }
            ),
        ]
        ok, matching = r._block_matches_vendor_payment(costs, "not_paid")
        self.assertTrue(ok)
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["bill"], "OPEN")
        ok_paid, _ = r._block_matches_vendor_payment(costs, "paid")
        self.assertFalse(ok_paid)

    def test_03_payment_filter_does_not_expand_incomplete_historical(self):
        r_all = self._report(vendor_payment_state="all")
        r_pay = self._report(vendor_payment_state="not_paid")
        self.assertNotIn("incomplete_historical", r_all._allowed_relation_classes())
        self.assertNotIn("incomplete_historical", r_pay._allowed_relation_classes())
        self.assertEqual(
            set(r_all._allowed_relation_classes()),
            set(r_pay._allowed_relation_classes()),
        )

    def test_04_draft_cancelled_not_in_open_domain(self):
        domain = open_vendor_bill_domain(company_ids=[self.company.id])
        self.assertIn(("state", "=", "posted"), domain)
        self.assertIn(("amount_residual", "!=", 0), domain)

    def test_05_vendor_pending_blocks_have_open_residual(self):
        r = self._report(vendor_payment_state="not_paid")
        for b in r._iter_sale_blocks():
            bills = [c for c in (b.get("costs") or []) if c.get("kind") == "bill"]
            self.assertTrue(bills)
            self.assertTrue(
                any(abs(c.get("residual") or c.get("residual_display") or 0) > 0.005 for c in bills)
            )
