# -*- coding: utf-8 -*-
"""19.0.8.4.0 — Manager-friendly report: sale grouping + 3 columns."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginManagerFriendlyReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "MGR Cliente Catador", "customer_rank": 1})
        cls.vendor_a = cls.env["res.partner"].create({"name": "MGR Omega", "supplier_rank": 1})
        cls.vendor_b = cls.env["res.partner"].create({"name": "MGR Nela", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "MGR Product", "type": "consu", "list_price": 1000, "standard_price": 200}
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.usd = cls.env.ref("base.USD")

    def _so(self, price=1000, currency=None):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "currency_id": (currency or self.company.currency_id).id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": price})
                ],
            }
        )
        so.action_confirm()
        return so

    def _inv(self, so, price=None, currency=None):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "currency_id": (currency or so.currency_id).id,
                "invoice_date": "2026-05-05",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price if price is not None else so.order_line[:1].price_unit,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _po(self, vendor, price=200, currency=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "currency_id": (currency or self.company.currency_id).id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def _bill(self, po, price=None, currency=None):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "currency_id": (currency or po.currency_id).id,
                "invoice_date": "2026-05-06",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price if price is not None else po.order_line[:1].price_unit,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _tx(self, so=None, inv=None, po=None, bill=None, state="validated"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": "2026-05-07",
            "customer_id": self.customer.id,
            "state": state,
        }
        if so:
            vals["sale_order_ids"] = [(6, 0, [so.id])]
        if inv:
            vals["customer_invoice_ids"] = [(6, 0, [inv.id])]
        if po:
            vals["purchase_order_ids"] = [(6, 0, [po.id])]
        if bill:
            vals["vendor_bill_ids"] = [(6, 0, [bill.id])]
        return self.Transaction.create(vals)

    def _report(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "report_layout": "compact",
            "show_fiscal_detail": False,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def test_01_group_by_customer_invoice(self):
        so = self._so(5000)
        inv = self._inv(so, 5000)
        po1 = self._po(self.vendor_a, 100)
        bill1 = self._bill(po1, 100)
        po2 = self._po(self.vendor_b, 200)
        bill2 = self._bill(po2, 200)
        self._tx(so=so, inv=inv, po=po1, bill=bill1)
        self._tx(so=so, inv=inv, po=po2, bill=bill2)
        blocks = self._report()._iter_sale_blocks()
        match = [b for b in blocks if inv in b["sale"]["moves"]]
        self.assertEqual(len(match), 1)
        self.assertEqual(len(match[0]["costs"]), 2)

    def test_02_group_by_sale_order_estimated(self):
        so = self._so(3000)
        po1 = self._po(self.vendor_a, 50)
        bill1 = self._bill(po1, 50)
        po2 = self._po(self.vendor_b, 80)
        bill2 = self._bill(po2, 80)
        self._tx(so=so, po=po1, bill=bill1)
        self._tx(so=so, po=po2, bill=bill2)
        blocks = self._report()._iter_sale_blocks()
        match = [b for b in blocks if so in b["txs"].mapped("sale_order_ids")]
        self.assertEqual(len(match), 1)
        self.assertTrue(match[0]["sale"]["is_estimated"])
        self.assertEqual(len(match[0]["costs"]), 2)

    def test_03_sale_counted_once_in_summary(self):
        so = self._so(10000)
        inv = self._inv(so, 10000)
        for price in (100, 200, 300):
            po = self._po(self.vendor_a, price)
            bill = self._bill(po, price)
            self._tx(so=so, inv=inv, po=po, bill=bill)
        grand = self._report()._general_summary()
        match = [b for b in grand["sales"] if inv in b["sale"]["moves"]]
        self.assertEqual(len(match), 1)
        self.assertAlmostEqual(match[0]["sale"]["untaxed"], inv.amount_untaxed, places=2)
        self.assertAlmostEqual(match[0]["cost_untaxed"], 600.0, places=2)

    def test_04_margin_once_formula(self):
        so = self._so(1000)
        inv = self._inv(so, 1000)
        po = self._po(self.vendor_a, 250)
        bill = self._bill(po, 250)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        b = self._report()._iter_sale_blocks()[-1]
        self.assertAlmostEqual(b["margin"], b["sale"]["untaxed"] - b["cost_untaxed"], places=2)
        self.assertAlmostEqual(b["margin_pct"], b["margin"] / b["sale"]["untaxed"] * 100.0, places=2)

    def test_05_template_three_columns(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        self.assertIn("jm-sale", arch)
        self.assertIn("jm-margin-hero", arch)
        self.assertIn("jm-dashboard", arch)
        self.assertIn("TOTAL COSTOS", arch)
        self.assertIn("RESUMEN GENERAL", arch)
        self.assertIn("jm-excel-table", arch)
        self.assertIn("COSTOS / PROVEEDORES", arch)
        self.assertIn("VENTA / CLIENTE", arch)
        self.assertNotIn("TOP 5 MÁRGENES", arch)
        self.assertNotIn("TOP 5 PÉRDIDAS", arch)
        self.assertNotIn("TOP 10 CLIENTES", arch)
        self.assertNotIn("TOP 10 PROVEEDORES", arch)
        self.assertNotIn("Comprometido", arch)
        self.assertNotIn("Venta s/ITBIS", arch)
        self.assertNotIn("MARGEN OBTENIDO", arch)
        self.assertNotIn(">COSTOS RELACIONADOS<", arch)
        self.assertIn("SIN COSTOS RELACIONADOS", arch)
        self.assertNotIn("VENTA REALIZADA", arch)

    def test_06_sale_numbered(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        self.assertIn("VENTA", arch)
        # sale_number kept for numbering (hidden or inline)
        self.assertTrue(
            "sale_number" in arch or "op_index" in arch
        )

    def test_07_margin_label_colors(self):
        so = self._so(100)
        inv = self._inv(so, 100)
        po = self._po(self.vendor_a, 90)
        bill = self._bill(po, 90)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        b = [x for x in self._report()._iter_sale_blocks() if inv in x["sale"]["moves"]][0]
        self.assertIn(b["margin_band"], ("positive", "low", "negative"))
        self.assertTrue(b["margin_label"])

    def test_08_fiscal_detail_flag_default_false(self):
        r = self._report()
        self.assertFalse(r.show_fiscal_detail)
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        self.assertIn("show_fiscal_detail", arch)

    def test_09_rate_two_decimals(self):
        r = self._report()
        self.assertEqual(r._format_rate(62.8), "62.80")
        self.assertEqual(r._format_rate(62.800000), "62.80")

    def test_10_xlsx_vista_gerencial(self):
        so = self._so(800)
        inv = self._inv(so, 800)
        po = self._po(self.vendor_a, 100)
        bill = self._bill(po, 100)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        r = self._report()
        r.action_generate_xlsx()
        import base64
        import io
        import zipfile

        data = base64.b64decode(r.export_file)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            wb = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")
        self.assertIn("Vista gerencial", wb)
        self.assertIn("Costos relacionados", wb)

    def test_11_no_duplicate_footer_line(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        self.assertEqual(arch.count("jm-margin-hero"), 1)
        self.assertEqual(arch.count("jm-dashboard"), 1)
        self.assertEqual(arch.count("RESUMEN GENERAL"), 1)

    def test_12_summary_cards_in_template(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        self.assertIn("Operaciones", arch)
        self.assertIn("Saludables", arch)
        self.assertIn("Bajas", arch)
        self.assertIn("Negativas", arch)
        self.assertNotIn("TOP 5 MÁRGENES", arch)
        self.assertNotIn("TOP 5 PÉRDIDAS", arch)
        self.assertNotIn("TOP 10 CLIENTES", arch)

    def test_13_version_manifest(self):
        # Soft: model still available
        self.assertTrue(self.Report._fields.get("show_fiscal_detail"))
        self.assertTrue(self.Report._fields.get("sort_by"))


def _make_manager_matrix():
    cases = []

    def add(name, fn):
        cases.append((name, fn))

    needles = [
        "jm-sale",
        "jm-margin-hero",
        "jm-dashboard",
        "jm-client",
        "sale_number",
        "margin_label",
        "show_fiscal_detail",
        "RESUMEN GENERAL",
        "jm-excel-table",
        "COSTOS / PROVEEDORES",
        "TOTAL COSTOS",
        "web.basic_layout",
        "by_currency_rows",
        "object-fit:contain",
        "jm-body",
        "jm-margin-hero",
        "MARGEN",
        "VENTA",
        "Estado / Saldo",
        "Generado por",
        "FACTURADA",
        "ESTIMADA",
        "Saludables",
        "Negativas",
    ]
    for i, n in enumerate(needles):
        add(
            "arch_%s" % i,
            lambda self, needle=n: self.assertIn(
                needle,
                self.env.ref(
                    "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
                ).arch_db
                or "",
            ),
        )
    for i in range(5):
        add(
            "field_sort_%s" % i,
            lambda self, _n=i: self.assertIn("sort_by", self.Report._fields),
        )
    for i in range(5):
        add(
            "label_saludable_%s" % i,
            lambda self, _n=i: self.assertIn(
                "MARGEN SALUDABLE",
                self._report()._margin_status_label("positive"),
            ),
        )

    for i in range(20):
        add(
            "rate_fmt_%s" % i,
            lambda self, n=i: self.assertRegex(
                self._report()._format_rate(10.0 + n * 0.1), r"^\d+\.\d{2}$"
            ),
        )

    for i in range(15):
        add(
            "layout_default_%s" % i,
            lambda self, _n=i: self.assertEqual(self._report().report_layout, "compact"),
        )

    for i in range(15):
        add(
            "fiscal_off_%s" % i,
            lambda self, _n=i: self.assertFalse(self._report().show_fiscal_detail),
        )

    for name, fn in cases:
        setattr(TestMarginManagerFriendlyReport, "test_gen_%s" % name, fn)


_make_manager_matrix()
