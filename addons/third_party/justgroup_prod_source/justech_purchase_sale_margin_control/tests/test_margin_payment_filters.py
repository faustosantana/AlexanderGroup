# -*- coding: utf-8 -*-
"""UAT unitario — filtros de pago/cobro 19.0.8.9.0."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginPaymentFilters(TransactionCase):
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
        }
        defaults.update(vals)
        return self.Report.create(defaults)

    def test_01_wizard_filter_fields_defaults(self):
        r = self._report()
        self.assertEqual(r.vendor_payment_state, "all")
        self.assertEqual(r.customer_payment_state, "all")
        self.assertEqual(r.finance_view, "all")
        self.assertEqual(r.vendor_doc_type, "all")
        self.assertEqual(r.date_basis, "operation")
        self.assertEqual(r.export_format, "pdf")

    def test_02_finance_view_sets_states(self):
        r = self._report()
        r.finance_view = "collected_vendor_pending"
        r._onchange_finance_view()
        self.assertEqual(r.vendor_payment_state, "not_paid")
        self.assertEqual(r.customer_payment_state, "paid")
        r.finance_view = "fully_closed"
        r._onchange_finance_view()
        self.assertEqual(r.vendor_payment_state, "paid")
        self.assertEqual(r.customer_payment_state, "paid")

    def test_03_pdf_arch_has_pago_saldo_columns(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("Estado / Saldo", arch)
        self.assertNotIn(">Abono/NC<", arch)
        self.assertIn("colspan=\"7\"", arch)
        self.assertIn("colspan=\"13\"", arch)
        self.assertNotIn(">NCF</th>", arch)
        self.assertIn("NCF:", arch)
        self.assertIn("CUENTAS POR PAGAR DEL REPORTE", arch)
        self.assertIn("FACTURADA", arch)
        self.assertIn("collection_badge", arch)
        self.assertIn("margin_state_short", arch)
        self.assertIn("_filter_header_lines", arch)
        self.assertIn("_format_report_date", arch)

    def test_04_wizard_form_has_generate_button(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_cost_vs_sale_report_form"
        )
        arch = view.arch_db or ""
        self.assertIn('name="action_preview"', arch)
        self.assertIn('name="action_download_pdf"', arch)
        self.assertIn("vendor_payment_state", arch)
        self.assertIn("customer_payment_state", arch)
        self.assertIn("finance_view", arch)
        self.assertIn("vendor_doc_type", arch)
        self.assertIn("date_basis", arch)
        self.assertIn("export_format", arch)

    def test_05_decorate_po_not_cxp(self):
        r = self._report()
        crow = r._decorate_cost_payment(
            {
                "kind": "po",
                "bill": "",
                "po": "P00175",
                "total": 1000.0,
                "residual": 0.0,
            }
        )
        self.assertIn("SIN FACTURA", crow["payment_badge"])
        self.assertIs(crow["residual_display"], False)
        self.assertIn("Sin factura", crow["doc_status"])

    def test_06_decorate_bill_payment_badges(self):
        r = self._report()
        for code, badge, residual in [
            ("not_paid", "PENDIENTE", 100.0),
            ("partial", "PARCIAL", 50.0),
            ("in_payment", "EN PROCESO", 100.0),
            ("paid", "PAGADA", 0.0),
        ]:
            crow = r._decorate_cost_payment(
                {
                    "kind": "bill",
                    "bill": "BILL/1",
                    "bill_id": 1,
                    "total": 100.0,
                    "residual": residual,
                    "raw_payment_state": code,
                }
            )
            self.assertEqual(crow["payment_badge"], badge, code)
            self.assertIsNot(crow["residual_display"], False)

        # residual 0 overrides technical in_payment → PAGADA (presentación)
        crow = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill": "BILL/2",
                "bill_id": 2,
                "total": 100.0,
                "residual": 0.0,
                "raw_payment_state": "in_payment",
            }
        )
        self.assertEqual(crow["payment_badge"], "PAGADA")

    def test_07_decorate_credit_note(self):
        r = self._report()
        crow = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill": "NC/1",
                "total": -500.0,
                "residual": 0.0,
                "raw_payment_state": "paid",
                "move_type": "in_refund",
            }
        )
        self.assertTrue(crow["is_credit_note"])
        self.assertIn("crédito", (crow["doc_status"] or "").lower())
        self.assertEqual(crow["abono_note"], "Nota de crédito")

    def test_08_customer_collection_labels(self):
        Move = self.env["account.move"]
        r = self._report()
        # empty sale
        sale = r._decorate_sale_collection({"moves": Move, "is_estimated": True})
        self.assertIn("Sin factura", sale["collection_badge"])

    def test_09_filter_header_two_lines(self):
        r = self._report(vendor_payment_state="not_paid")
        lines = r._filter_header_lines()
        l1, l2 = lines[0], lines[1]
        self.assertIn("Período", l1)
        self.assertIn("Estado proveedor", l2)
        self.assertIn("Pendientes", l2)
        self.assertIn("Operaciones", lines[2] if len(lines) > 2 else l2)

    def test_10_summary_includes_payment_stats(self):
        r = self._report()
        summary = r._general_summary()
        for key in (
            "bill_count",
            "bill_pending",
            "bill_paid",
            "vendor_residual",
            "cxp_rows",
            "filter_line1",
            "filter_line2",
        ):
            self.assertIn(key, summary)

    def test_11_po_only_filter_excludes_bills_ops(self):
        r_all = self._report()
        all_blocks = r_all._iter_sale_blocks()
        r_po = self._report(vendor_doc_type="po_only")
        po_blocks = r_po._iter_sale_blocks()
        for b in po_blocks:
            self.assertTrue(all(c.get("kind") == "po" for c in b["costs"] if not c.get("__empty")))
        # po set ⊆ all set size
        self.assertLessEqual(len(po_blocks), len(all_blocks))

    def test_12_vendor_pending_filter_only_matching_codes(self):
        r = self._report(vendor_payment_state="not_paid")
        for b in r._iter_sale_blocks():
            for c in b.get("costs") or []:
                if c.get("kind") == "bill":
                    residual = abs(
                        c.get("residual_display")
                        if c.get("residual_display") is not False
                        else (c.get("residual") or 0.0)
                    )
                    self.assertGreater(residual, 0.005)

    def test_13_cost_rows_expose_raw_payment_state(self):
        Tx = self.env["purchase.sale.margin.transaction"]
        tx = Tx.search(
            [("vendor_bill_ids", "!=", False), ("company_id", "=", self.company.id)],
            limit=1,
        )
        if not tx:
            self.skipTest("No vendor bill transactions in DB")
        rows = self.Report._cost_rows(tx)
        bill_rows = [x for x in rows if x.get("kind") == "bill"]
        self.assertTrue(bill_rows)
        self.assertIn("raw_payment_state", bill_rows[0])
        self.assertIn("partner_id", bill_rows[0])
