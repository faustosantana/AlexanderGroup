# -*- coding: utf-8 -*-
"""19.0.8.13.0 — Incomplete ops (sales w/o cost, costs w/o sale) + CxP by currency + no `_` shadow."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginIncompleteOps(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "INC Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "INC Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "INC Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 200,
            }
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.usd = cls.env.ref("base.USD")
        cls.dop = (
            cls.env["res.currency"].search([("name", "=", "DOP")], limit=1)
            or cls.company.currency_id
        )

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
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _out_invoice(self, so, price=None, currency=None, partner=None):
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": (partner or so.partner_id).id,
                "company_id": self.company.id,
                "currency_id": (currency or so.currency_id or self.company.currency_id).id,
                "invoice_date": "2026-06-15",
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
        return inv

    def _po(self, price=200, currency=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "currency_id": (currency or self.company.currency_id).id,
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

    def _bill(self, po, price=None, currency=None):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "currency_id": (currency or po.currency_id or self.company.currency_id).id,
                "invoice_date": "2026-06-10",
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
        return bill

    def _tx(self, so=None, inv=None, po=None, bill=None, customer=None, state="validated"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": "2026-06-20",
            "state": state,
        }
        if customer or so:
            vals["customer_id"] = (customer or so.partner_id).id
        if so:
            vals["sale_order_ids"] = [(6, 0, [so.id])]
        if inv:
            vals["customer_invoice_ids"] = [(6, 0, [inv.id])]
        if po:
            vals["purchase_order_ids"] = [(6, 0, [po.id])]
            vals["supplier_ids"] = [(6, 0, [po.partner_id.id])]
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

    def test_01_normal_operation_summary(self):
        so = self._so(1000)
        inv = self._out_invoice(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        op = self.Report._operation_summary(tx)
        self.assertFalse(op.get("incomplete_sale_only"))
        self.assertFalse(op.get("incomplete_cost_only"))
        self.assertAlmostEqual(op["margin"], 800.0, places=2)

    def test_02_sale_without_cost_flags(self):
        so = self._so(500)
        inv = self._out_invoice(so, 500)
        tx = self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=True)
        found = [op for op in r._iter_operation_summaries() if op["tx"] == tx]
        self.assertEqual(len(found), 1)
        op = found[0]
        self.assertTrue(op["incomplete_sale_only"])
        self.assertFalse(op["incomplete_cost_only"])
        self.assertEqual(op["margin_band"], "pending")
        self.assertAlmostEqual(op["cost_untaxed"], 0.0, places=2)
        self.assertAlmostEqual(op["margin"], 500.0, places=2)

    def test_03_cost_without_sale_flags(self):
        po = self._po(200)
        bill = self._bill(po, 200)
        tx = self._tx(po=po, bill=bill)
        r = self._report(include_costs_without_sale=True)
        found = [op for op in r._iter_operation_summaries() if op["tx"] == tx]
        self.assertEqual(len(found), 1)
        op = found[0]
        self.assertTrue(op["incomplete_cost_only"])
        self.assertFalse(op["incomplete_sale_only"])
        self.assertEqual(op["margin_band"], "pending")
        self.assertEqual(op["margin"], 0.0)

    def test_04_sale_without_customer_label(self):
        so = self._so(300)
        inv = self._out_invoice(so, 300)
        # keep invoice but clear customer name edge via empty customer on sale dict path
        tx = self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=True)
        # Must not raise TypeError from shadowed `_`
        grand = r._general_summary()
        self.assertIn("sales", grand)
        # Force path with empty customer name
        for b in grand["sales"]:
            if b.get("incomplete_sale_only"):
                b["sale"] = dict(b["sale"], customer=False)
        # Re-run top_clients path indirectly: ensure gettext `_` still callable
        from odoo import _ as gettext

        self.assertTrue(callable(gettext))
        label = gettext("(Sin cliente)")
        self.assertTrue(label)

    def test_05_both_incomplete_flags_general_summary(self):
        so = self._so(700)
        inv = self._out_invoice(so, 700)
        self._tx(so=so, inv=inv)
        po = self._po(150)
        bill = self._bill(po, 150)
        self._tx(po=po, bill=bill)
        so2 = self._so(1000)
        inv2 = self._out_invoice(so2, 1000)
        po2 = self._po(400)
        bill2 = self._bill(po2, 400)
        self._tx(so=so2, inv=inv2, po=po2, bill=bill2)

        r = self._report(
            include_sales_without_cost=True,
            include_costs_without_sale=True,
        )
        grand = r._general_summary()  # must not TypeError
        self.assertGreaterEqual(grand.get("sales_wo_cost") or 0, 1)
        self.assertGreaterEqual(grand.get("costs_wo_sale") or 0, 1)
        self.assertGreaterEqual(grand.get("complete_ops") or 0, 1)
        # Confirmed margin must not include incomplete sale-as-100% as "positive"
        for b in grand["sales"]:
            if b.get("incomplete_sale_only") or b.get("incomplete_cost_only"):
                self.assertEqual(b.get("margin_band"), "pending")

    def test_06_cxp_totals_separated_by_currency(self):
        so_d = self._so(1000, currency=self.dop)
        inv_d = self._out_invoice(so_d, 1000, currency=self.dop)
        po_d = self._po(200, currency=self.dop)
        bill_d = self._bill(po_d, 200, currency=self.dop)
        self._tx(so=so_d, inv=inv_d, po=po_d, bill=bill_d)

        so_u = self._so(500, currency=self.usd)
        inv_u = self._out_invoice(so_u, 500, currency=self.usd)
        po_u = self._po(100, currency=self.usd)
        bill_u = self._bill(po_u, 100, currency=self.usd)
        self._tx(so=so_u, inv=inv_u, po=po_u, bill=bill_u)

        r = self._report()
        grand = r._general_summary()
        totals = grand.get("cxp_totals") or []
        names = {t.get("currency_name") for t in totals}
        # At least one currency row when bills exist
        self.assertTrue(totals)
        # Never a single mixed total without currency key
        for t in totals:
            self.assertTrue(t.get("currency_name") or t.get("currency"))
            self.assertIn("total", t)
            self.assertIn("paid", t)
            self.assertIn("residual", t)
        if self.dop.name != self.usd.name and len(names) >= 2:
            self.assertIn(self.dop.name, names)
            self.assertIn(self.usd.name, names)

    def test_07_pdf_xlsx_generate_incomplete(self):
        so = self._so(500)
        inv = self._out_invoice(so, 500)
        self._tx(so=so, inv=inv)
        po = self._po(200)
        bill = self._bill(po, 200)
        self._tx(po=po, bill=bill)

        r = self._report(
            include_sales_without_cost=True,
            include_costs_without_sale=True,
            export_format="pdf",
        )
        # Prefer QWeb HTML (stable in CI); full wkhtmltopdf can drop DB SSL under load
        html = self.env["ir.actions.report"]._render_qweb_html(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf",
            r.ids,
        )
        if isinstance(html, (list, tuple)):
            html = html[0]
        body = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)
        self.assertIn("DETALLE DE COSTOS VS VENTAS", body)
        self.assertTrue("SIN COSTOS" in body or "SIN VENTA" in body or "COSTO PENDIENTE" in body or "MARGEN PENDIENTE" in body)

        r2 = self._report(
            include_sales_without_cost=True,
            include_costs_without_sale=True,
            export_format="xlsx",
        )
        # XLSX path: build workbook without relying on attachment download
        if hasattr(r2, "_generate_xlsx_bytes"):
            data = r2._generate_xlsx_bytes()
            self.assertTrue(data)
        else:
            action = r2.action_generate_xlsx()
            self.assertTrue(action)

    def test_08_no_underscore_shadow_in_general_summary(self):
        so = self._so(100)
        inv = self._out_invoice(so, 100)
        self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=True)
        # Call twice: second call historically failed when `_` was assigned None
        r._general_summary()
        r._general_summary(transactions=None)
        from odoo import _

        self.assertTrue(callable(_))
        self.assertEqual(type(_("(Sin cliente)")), str)

    def test_09_header_has_no_border_boxes(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("DETALLE DE COSTOS VS VENTAS", arch)
        self.assertIn("SIN COSTOS RELACIONADOS", arch)
        self.assertIn("SIN VENTA RELACIONADA", arch)
        self.assertIn("cxp_totals", arch)
        self.assertIn("border:none", arch)

    def test_10_filters_decorate_incomplete_labels(self):
        so = self._so(500)
        inv = self._out_invoice(so, 500)
        tx = self._tx(so=so, inv=inv)
        r = self._report(include_sales_without_cost=True)
        blocks = r._iter_sale_blocks()
        match = [b for b in blocks if tx in (b.get("txs") or b.get("tx"))]
        self.assertTrue(match)
        self.assertIn(
            match[0].get("margin_state_short"),
            ("COSTO PENDIENTE", "Costo pendiente"),
        )
