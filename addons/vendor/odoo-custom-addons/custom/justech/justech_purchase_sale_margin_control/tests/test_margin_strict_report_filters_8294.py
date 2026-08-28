# -*- coding: utf-8 -*-
"""19.0.8.29.4 — Strict operation-class filters; payment never broadens class."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginStrictReportFilters8294(TransactionCase):
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

    def test_01_complete_allowed_excludes_cost_without_sale(self):
        r = self._report(show_complete=True, vendor_payment_state="not_paid")
        allowed = r._allowed_relation_classes()
        self.assertIn("complete", allowed)
        self.assertIn("partial_with_cost", allowed)
        self.assertNotIn("incomplete_historical", allowed)

    def test_02_payment_never_broadens_class_scope(self):
        r_all = self._report(vendor_payment_state="all")
        r_pay = self._report(vendor_payment_state="not_paid")
        self.assertEqual(
            set(r_all._allowed_relation_classes()),
            set(r_pay._allowed_relation_classes()),
        )
        self.assertNotIn("incomplete_historical", r_pay._allowed_relation_classes())

    def test_03_cost_without_sale_only_classes(self):
        r = self._report(
            show_complete=False,
            show_costs_without_sale=True,
            vendor_payment_state="not_paid",
        )
        self.assertEqual(r._allowed_relation_classes(), ["incomplete_historical"])

    def test_04_union_complete_and_cost_without_sale(self):
        r = self._report(
            show_complete=True,
            show_costs_without_sale=True,
            vendor_payment_state="all",
        )
        allowed = set(r._allowed_relation_classes())
        self.assertIn("complete", allowed)
        self.assertIn("incomplete_historical", allowed)

    def test_05_complete_blocks_have_no_sin_venta(self):
        r = self._report(show_complete=True, vendor_payment_state="not_paid")
        for b in r._get_filtered_report_blocks():
            self.assertFalse(b.get("incomplete_cost_only"))

    def test_06_pending_still_residual_based(self):
        r = self._report()
        open_bill = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill_id": 1,
                "bill": "B1",
                "total": 100.0,
                "residual": 25.0,
                "raw_payment_state": "partial",
            }
        )
        self.assertTrue(r._cost_matches_vendor_payment(open_bill, "not_paid"))
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

    def test_07_filtered_helper_matches_iter(self):
        r = self._report(show_complete=True, vendor_payment_state="all")
        a = r._iter_sale_blocks()
        b = r._get_filtered_report_blocks()
        self.assertEqual(len(a), len(b))

    def test_08_scope_label_complete_only(self):
        r = self._report(show_complete=True)
        self.assertIn("Completas", r._report_scope_label())
        self.assertNotIn("Costos sin venta", r._report_scope_label())
