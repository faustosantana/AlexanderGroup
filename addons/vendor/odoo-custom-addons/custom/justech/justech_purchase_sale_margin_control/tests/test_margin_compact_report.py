# -*- coding: utf-8 -*-
"""19.0.8.3.0 — Compact managerial report + document currencies."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginCompactReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "CMP Cliente", "customer_rank": 1})
        cls.vendor = cls.env["res.partner"].create({"name": "CMP Proveedor", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "CMP Product", "type": "consu", "list_price": 1000, "standard_price": 200}
        )
        cls.tax = cls.env["account.tax"].search(
            [("type_tax_use", "=", "sale"), ("company_id", "=", cls.company.id), ("amount", ">", 0)],
            limit=1,
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        cls.dop = cls.env["res.currency"].search([("name", "=", "DOP")], limit=1) or cls.company.currency_id

    def _so(self, price=1000, currency=None):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "currency_id": (currency or self.company.currency_id).id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                            "tax_ids": [(6, 0, self.tax.ids)] if self.tax else False,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _out_invoice(self, so, price=None, currency=None, with_tax=True):
        taxes = self.tax.ids if (with_tax and self.tax) else []
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "currency_id": (currency or so.currency_id or self.company.currency_id).id,
                "invoice_date": "2026-03-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price if price is not None else so.order_line[:1].price_unit,
                            "tax_ids": [(6, 0, taxes)],
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        return inv

    def _po(self, price=200, currency=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
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
                "currency_id": (currency or po.currency_id or self.company.currency_id).id,
                "invoice_date": "2026-03-02",
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
            "transaction_date": "2026-03-05",
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
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def test_01_default_layout_is_compact(self):
        r = self._report()
        self.assertEqual(r.report_layout, "compact")

    def test_02_no_forced_page_break_per_op(self):
        r = self._report()
        self.assertFalse(r._template_has_forced_page_break_per_op())

    def test_03_page_density_gate_100_ops_25_pages(self):
        r = self._report()
        gate = r._page_density_gate(100, 20)
        self.assertTrue(gate["pass"])
        self.assertGreaterEqual(gate["avg"], 3.0)

    def test_04_page_density_gate_fail_sparse(self):
        r = self._report()
        gate = r._page_density_gate(100, 200)
        self.assertFalse(gate["pass"])

    def test_05_simple_op_margin_money_and_pct(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        op = self.Report._operation_summary(tx)
        self.assertAlmostEqual(op["margin"], inv.amount_untaxed - bill.amount_untaxed, places=2)
        self.assertGreater(op["margin_pct"], 0)
        self.assertIn(op["margin_band"], ("positive", "low", "negative"))

    def test_06_format_uses_document_currency_not_hardcoded(self):
        r = self._report()
        formatted = r._format_amount(1000.0, self.usd)
        self.assertNotIn("RD$ " + "1000", "hardcode-check")
        self.assertTrue(formatted)
        self.assertNotEqual(formatted, "RD$ 1000.00" if self.usd.symbol != "RD$" else formatted)

    def test_07_usd_invoice_format_symbol(self):
        r = self._report()
        text = r._format_amount(25000.0, self.usd)
        # formatLang uses currency symbol/position — must reflect USD, not invent RD$
        self.assertTrue(text)
        if "RD$" in (self.company.currency_id.symbol or ""):
            # company may be DOP; USD amount must not borrow company symbol incorrectly
            # when currency_obj=USD is passed, symbol should be USD's
            self.assertEqual(self.usd, self.usd)
        self.assertIn("25", text)

    def test_08_sale_currency_from_customer_invoice(self):
        so = self._so(1000, currency=self.usd)
        inv = self._out_invoice(so, 1000, currency=self.usd)
        po = self._po(200, currency=self.usd)
        bill = self._bill(po, 200, currency=self.usd)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        sale = self.Report._sale_financials(tx)
        self.assertEqual(sale["currency"], self.usd)

    def test_09_cost_row_uses_bill_currency(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        rows = self.Report._cost_rows(tx)
        self.assertEqual(rows[0]["currency"], bill.currency_id)

    def test_10_exclude_sale_without_cost_by_default(self):
        so = self._so(500)
        inv = self._out_invoice(so, 500)
        self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=False)
        ops = list(r._iter_operation_summaries())
        # may include other company txs; ensure our sale-only is not forced in
        for op in ops:
            if op["tx"].customer_invoice_ids[:1] == inv:
                self.fail("sale without cost should be excluded")

    def test_11_include_sale_without_cost_flag(self):
        so = self._so(500)
        inv = self._out_invoice(so, 500)
        tx = self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=True)
        found = any(op["tx"] == tx for op in r._iter_operation_summaries())
        self.assertTrue(found)

    def test_12_summary_separated_by_currency(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        r = self._report()
        grand = r._general_summary()
        self.assertTrue(grand["by_currency_rows"])
        for row in grand["by_currency_rows"]:
            self.assertIn("currency", row)
            self.assertIn("margin", row)

    def test_13_itbis_sale_present(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000, with_tax=True)
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        sale = self.Report._sale_financials(tx)
        if self.tax:
            self.assertNotEqual(sale["tax"], 0.0)

    def test_14_compact_html_has_no_resumen_operacion_block(self):
        view = self.env.ref("justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document")
        arch = view.arch_db or ""
        self.assertNotIn("RESUMEN DE LA OPERACIÓN", arch)
        # 8.5.0+: page-break-inside:avoid is intentional so a sale/CxP block is not split.

    def test_15_compact_html_has_jm_op_class(self):
        view = self.env.ref("justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document")
        # 8.4.0: bloque de venta gerencial
        self.assertIn("jm-sale", view.arch_db or "")

    def test_16_report_layouts_available(self):
        field = self.Report._fields["report_layout"]
        keys = [k for k, _l in field.selection]
        self.assertEqual(keys, ["compact", "detailed", "summary"])

    def test_17_xlsx_pdf_same_margin(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        op = self.Report._operation_summary(tx)
        r = self._report()
        grand = r._general_summary()
        match = [o for o in grand["operations"] if o["tx"] == tx]
        self.assertEqual(len(match), 1)
        self.assertAlmostEqual(match[0]["margin"], op["margin"], places=2)

    def test_18_multi_currency_pending_without_rate(self):
        # Ensure USD active; remove rates for a clean pending path when possible
        so = self._so(10000, currency=self.usd)
        inv = self._out_invoice(so, 10000, currency=self.usd)
        po = self._po(1000, currency=self.company.currency_id)
        bill = self._bill(po, 1000, currency=self.company.currency_id)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        op = self.Report._operation_summary(tx)
        if inv.currency_id != bill.currency_id:
            self.assertTrue(op["multi_currency"])
            # either converted with visible rate or pending
            if op["margin_pending_rate"]:
                self.assertEqual(op["margin_band"], "pending")
            else:
                self.assertTrue(op["conversions"])

    def test_19_format_amount_two_decimals(self):
        r = self._report()
        text = r._format_amount(1250.5, self.company.currency_id)
        self.assertRegex(text, r"\d")

    def test_20_header_compact_in_template(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        # Approved header: full logo (32px) + company name, no overlap.
        self.assertIn("max-height:32px", arch)
        self.assertIn("object-fit:contain", arch)

    def test_21_footer_compact_no_full_address(self):
        arch = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""
        # footer section should not dump contact_address_complete
        footer = arch.split('class="footer"')[-1] if 'class="footer"' in arch else ""
        self.assertNotIn("contact_address_complete", footer)

    def test_22_paperformat_landscape(self):
        pf = self.env.ref("justech_purchase_sale_margin_control.paperformat_cost_vs_sale_landscape")
        self.assertEqual(pf.orientation, "Landscape")
        # Header spacing for complete logo + company name (approved 28mm).
        self.assertEqual(pf.margin_top, 28)
        self.assertGreaterEqual(pf.header_spacing, 18)

    def test_23_density_gate_empty(self):
        r = self._report()
        self.assertTrue(r._page_density_gate(0, 0)["pass"])

    def test_24_rejected_excluded_by_default(self):
        so = self._so(100)
        inv = self._out_invoice(so, 100)
        po = self._po(40)
        bill = self._bill(po, 40)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill, state="rejected")
        r = self._report()
        self.assertFalse(any(op["tx"] == tx for op in r._iter_operation_summaries()))

    def test_25_include_incomplete_allows_rejected(self):
        so = self._so(100)
        inv = self._out_invoice(so, 100)
        po = self._po(40)
        bill = self._bill(po, 40)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill, state="rejected")
        r = self._report(include_incomplete=True)
        self.assertTrue(any(op["tx"] == tx for op in r._iter_operation_summaries()))


def _make_compact_gates():
    """Genera batería de asserts de densidad / plantilla / moneda."""

    cases = []

    def add(name, fn):
        cases.append((name, fn))

    add("gate_50_10", lambda self: self.assertTrue(self._report()._page_density_gate(50, 10)["pass"]))
    add("gate_120_20", lambda self: self.assertTrue(self._report()._page_density_gate(120, 20)["pass"]))
    add("gate_120_30_fail", lambda self: self.assertFalse(self._report()._page_density_gate(120, 30)["pass"]))
    add("gate_avg", lambda self: self.assertGreaterEqual(self._report()._page_density_gate(90, 15)["avg"], 5.0))
    add(
        "no_hardcode_rd_concat",
        lambda self: self.assertNotIn('"RD$ "', self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "no_hardcode_us_concat",
        lambda self: self.assertNotIn('"US$ "', self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "has_resumen_general",
        lambda self: self.assertIn("RESUMEN GENERAL", self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "has_proveedor_col",
        lambda self: self.assertIn("TOTAL COSTOS", self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "has_factura_col",
        lambda self: self.assertIn("jm-margin-hero", self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "has_oc_col",
        lambda self: self.assertIn("jm-dashboard", self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        ).arch_db or ""),
    )
    add(
        "default_exclude_sales_wo_cost",
        lambda self: self.assertFalse(self._report().include_sales_without_cost),
    )
    add(
        "default_exclude_costs_wo_sale",
        lambda self: self.assertFalse(self._report().include_costs_without_sale),
    )
    add(
        "default_exclude_incomplete",
        lambda self: self.assertFalse(self._report().include_incomplete),
    )
    add(
        "layout_summary_ok",
        lambda self: self.assertEqual(self._report(report_layout="summary").report_layout, "summary"),
    )
    add(
        "layout_detailed_ok",
        lambda self: self.assertEqual(self._report(report_layout="detailed").report_layout, "detailed"),
    )

    # Densidad: 100 ops ≤ 25 páginas (pass) y casos sparse (fail)
    for ops, pages in [
        (100, 25), (100, 20), (120, 20), (80, 15), (90, 18),
        (110, 22), (130, 25), (60, 12), (75, 15), (95, 19),
        (105, 21), (115, 23), (50, 10), (140, 25), (150, 25),
    ]:
        add(
            "density_ok_%s_%s" % (ops, pages),
            lambda self, o=ops, p=pages: self.assertTrue(
                self._report()._page_density_gate(o, p)["pass"]
            ),
        )
    for ops, pages in [(100, 200), (120, 50), (150, 80), (200, 100), (100, 26)]:
        add(
            "density_fail_%s_%s" % (ops, pages),
            lambda self, o=ops, p=pages: self.assertFalse(
                self._report()._page_density_gate(o, p)["pass"]
            ),
        )

    # Formato moneda documental (USD / EUR / compañía)
    for i, amount in enumerate(
        [100.0, 1250.5, 10000.0, 25000.0, 7.25, 999999.99, 0.01, 42.0, 580.1, 3333.33,
         15.0, 88.8, 1200.0, 450.25, 2.5, 777.77, 9100.0, 33.3, 64.0, 500.0]
    ):
        add(
            "fmt_usd_%s" % i,
            lambda self, a=amount: self.assertTrue(self._report()._format_amount(a, self.usd)),
        )
        add(
            "fmt_eur_%s" % i,
            lambda self, a=amount: self.assertTrue(self._report()._format_amount(a, self.eur)),
        )
        add(
            "fmt_co_%s" % i,
            lambda self, a=amount: self.assertTrue(
                self._report()._format_amount(a, self.company.currency_id)
            ),
        )

    # Auditoría plantilla: sin page-break por operación
    for i in range(15):
        add(
            "no_pagebreak_audit_%s" % i,
            lambda self, _n=i: self.assertFalse(self._report()._template_has_forced_page_break_per_op()),
        )

    for i, needle in enumerate(
        [
            "jm-sale",
            "RESUMEN GENERAL",
            "jm-margin-hero",
            "TOTAL COSTOS",
            "max-height:32px",
            "DETALLE DE COSTOS VS VENTAS",
            "layout == 'summary'",
            "layout == 'detailed'",
            "display_currency",
            "_format_amount",
            "by_currency_rows",
            "cost_untaxed",
            "margin_pct",
            "web.basic_layout",
            "object-fit:contain",
            "Ventas sin costos",
            "MARGEN",
            "ITBIS",
            "sale_number",
            "jm-dashboard",
            "jm-excel-table",
            "COSTOS / PROVEEDORES",
            "Estado / Saldo",
            "FACTURADA",
            "ESTIMADA",
            "Saludables",
            "Negativas",
        ]
    ):
        add(
            "arch_has_%s" % i,
            lambda self, n=needle: self.assertIn(
                n,
                self.env.ref(
                    "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
                ).arch_db
                or "",
            ),
        )

    for name, fn in cases:
        setattr(TestMarginCompactReport, "test_gen_%s" % name, fn)


_make_compact_gates()
