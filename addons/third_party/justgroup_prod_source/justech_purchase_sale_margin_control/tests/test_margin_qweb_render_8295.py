# -*- coding: utf-8 -*-
"""19.0.8.29.5 — QWeb render context must not mutate mid-render."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginQwebRender8295(TransactionCase):
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

    def test_01_prepare_qweb_grand_has_sales_and_operations(self):
        r = self._report()
        grand = r._prepare_qweb_grand()
        self.assertIsInstance(grand, dict)
        self.assertIn("sales", grand)
        self.assertIn("operations", grand)
        self.assertIsInstance(grand["sales"], list)
        self.assertIsInstance(grand["operations"], list)
        self.assertIs(grand["sales"], grand["operations"])

    def test_02_prepare_does_not_mutate_on_reaccess(self):
        r = self._report(vendor_payment_state="not_paid")
        grand = r._prepare_qweb_grand()
        keys_before = set(grand.keys())
        len_before = len(grand)
        # Simulate QWeb non-mutating expression
        sales = grand.get("sales") or grand.get("operations") or []
        _ = list(sales)
        self.assertEqual(set(grand.keys()), keys_before)
        self.assertEqual(len(grand), len_before)

    def test_03_template_uses_non_mutating_sales_expr(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("_prepare_qweb_grand", arch)
        self.assertIn("grand.get('sales') or grand.get('operations') or []", arch)
        self.assertNotIn("grand['operations']", arch)
        self.assertNotIn("grand['by_currency_rows']", arch)
        self.assertNotIn("grand['cxp_rows']", arch)

    def test_04_html_render_pending(self):
        r = self._report(
            show_complete=False,
            show_costs_without_sale=True,
            vendor_payment_state="not_paid",
        )
        before = [id(b) for b in (r._get_filtered_report_blocks() or [])]
        html = self.env["ir.actions.report"]._render_qweb_html(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf",
            r.ids,
        )
        body = html[0] if isinstance(html, tuple) else html
        self.assertTrue(body)
        after = [id(b) for b in (r._get_filtered_report_blocks() or [])]
        self.assertEqual(len(before), len(after))

    def test_05_complete_only_no_sin_venta_in_html(self):
        r = self._report(show_complete=True, vendor_payment_state="not_paid")
        for b in r._get_filtered_report_blocks():
            self.assertFalse(b.get("incomplete_cost_only"))
