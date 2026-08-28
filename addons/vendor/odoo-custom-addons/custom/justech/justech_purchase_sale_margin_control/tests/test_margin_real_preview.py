# -*- coding: utf-8 -*-
"""19.0.8.21.0 — Preview HTML real: no descarga; mismo dataset que PDF/XLSX."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _is_direct_download(action):
    """True si la acción dispara descarga de archivo en el cliente Owl."""
    if not action:
        return False
    url = action.get("url") or ""
    if action.get("type") == "ir.actions.act_url" and "download=true" in url:
        return True
    if action.get("type") == "ir.actions.report" and action.get("report_type") in (
        "qweb-pdf",
        "qweb-text",
    ):
        return True
    return False


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginRealPreview(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other = cls.env["res.company"].search(
            [("id", "!=", cls.company.id)], limit=1
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "PREV Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "PREV Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "PREV Product",
                "type": "consu",
                "is_storable": True,
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

    def _so(self, price=1000):
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
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _inv(self, so, price=None):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price
                            if price is not None
                            else so.order_line[:1].price_unit,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _po(self, price=200):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": price,
                            "cost_usage_type": "resale_direct",
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _bill(self, po, price=None):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price
                            if price is not None
                            else po.order_line[:1].price_unit,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _tx(self, so=None, inv=None, po=None, bill=None, date="2026-06-20"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": date,
            "state": "validated",
            "is_uat_fixture": True,
        }
        if so:
            vals["customer_id"] = so.partner_id.id
            vals["sale_order_ids"] = [(6, 0, [so.id])]
        if inv:
            vals["customer_invoice_ids"] = [(6, 0, [inv.id])]
        if po:
            vals["purchase_order_ids"] = [(6, 0, [po.id])]
            vals["supplier_ids"] = [(6, 0, [po.partner_id.id])]
        if bill:
            vals["vendor_bill_ids"] = [(6, 0, [bill.id])]
        return self.Transaction.with_context(allow_parallel_margin_tx=True).create(vals)

    def _report(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "only_uat": True,
            "show_complete": True,
            "show_sales_without_cost": True,
            "show_costs_without_sale": True,
            "show_incomplete": True,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def _html(self, report):
        html = self.env["ir.actions.report"]._render_qweb_html(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf",
            report.ids,
        )
        if isinstance(html, (list, tuple)):
            html = html[0]
        return html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)

    def _complete_fixture(self):
        so = self._so(1000)
        inv = self._inv(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        return self._tx(so=so, inv=inv, po=po, bill=bill)

    def test_01_preview_does_not_download(self):
        self._complete_fixture()
        action = self._report().action_preview()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-html")
        self.assertFalse(action.get("close_on_report_download"))
        self.assertFalse(_is_direct_download(action))
        self.assertIn("report_cost_vs_sale_pdf", action.get("report_name") or "")

    def test_02_download_pdf_is_pdf(self):
        self._complete_fixture()
        action = self._report().action_download_pdf()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-pdf")
        self.assertTrue(_is_direct_download(action))

    def test_03_download_xlsx_is_xlsx(self):
        self._complete_fixture()
        r = self._report()
        action = r.action_download_xlsx()
        self.assertEqual(action.get("type"), "ir.actions.act_url")
        self.assertIn("download=true", action.get("url") or "")
        self.assertTrue(r.export_file)
        self.assertTrue((r.export_filename or "").endswith(".xlsx"))

    def test_04_preview_not_same_action_as_pdf(self):
        self._complete_fixture()
        r = self._report()
        preview = r.action_preview()
        pdf = r.action_download_pdf()
        self.assertEqual(preview.get("report_name"), pdf.get("report_name"))
        self.assertNotEqual(preview.get("report_type"), pdf.get("report_type"))

    def test_05_same_dataset_preview_pdf_xlsx(self):
        self._complete_fixture()
        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        self._tx(so=so_s, inv=inv_s)
        r = self._report()
        n = len(r._general_summary().get("operations") or [])
        self.assertGreaterEqual(n, 2)
        body = self._html(r)
        self.assertIn("RESUMEN GENERAL", body)
        self.assertIn("Operaciones:", body)
        data = r._generate_xlsx_bytes()
        self.assertTrue(data)
        self.assertGreater(len(data), 100)
        n2 = len(r._general_summary().get("operations") or [])
        self.assertEqual(n, n2)

    def test_06_scope_completas(self):
        complete = self._complete_fixture()
        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        sale_only = self._tx(so=so_s, inv=inv_s)
        r = self._report(
            show_complete=True,
            show_sales_without_cost=False,
            show_costs_without_sale=False,
            show_incomplete=False,
        )
        ids = {tx.id for b in r._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(complete.id, ids)
        self.assertNotIn(sale_only.id, ids)
        self.assertFalse(_is_direct_download(r.action_preview()))

    def test_07_scope_ventas_sin_costos(self):
        complete = self._complete_fixture()
        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        sale_only = self._tx(so=so_s, inv=inv_s)
        r = self._report(
            show_complete=False,
            show_sales_without_cost=True,
            show_costs_without_sale=False,
            show_incomplete=False,
        )
        ids = {tx.id for b in r._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(sale_only.id, ids)
        self.assertNotIn(complete.id, ids)

    def test_08_scope_costos_sin_venta(self):
        complete = self._complete_fixture()
        po_k = self._po(150)
        bill_k = self._bill(po_k, 150)
        cost_only = self._tx(po=po_k, bill=bill_k)
        r = self._report(
            show_complete=False,
            show_sales_without_cost=False,
            show_costs_without_sale=True,
            show_incomplete=False,
        )
        ids = {tx.id for b in r._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(cost_only.id, ids)
        self.assertNotIn(complete.id, ids)

    def test_09_scope_incompletas_and_combined(self):
        complete = self._complete_fixture()
        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        sale_only = self._tx(so=so_s, inv=inv_s)
        po_k = self._po(150)
        bill_k = self._bill(po_k, 150)
        cost_only = self._tx(po=po_k, bill=bill_k)
        r_combo = self._report(
            show_complete=True,
            show_sales_without_cost=True,
            show_costs_without_sale=False,
            show_incomplete=False,
        )
        ids = {tx.id for b in r_combo._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(complete.id, ids)
        self.assertIn(sale_only.id, ids)
        self.assertNotIn(cost_only.id, ids)
        r_sc = self._report(
            show_complete=False,
            show_sales_without_cost=True,
            show_costs_without_sale=True,
            show_incomplete=False,
        )
        ids_sc = {tx.id for b in r_sc._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(sale_only.id, ids_sc)
        self.assertIn(cost_only.id, ids_sc)
        self.assertNotIn(complete.id, ids_sc)
        r_all = self._report()
        ids_all = {tx.id for b in r_all._iter_sale_blocks() for tx in b["txs"]}
        self.assertTrue({complete.id, sale_only.id, cost_only.id} <= ids_all)
        n = len(r_all._general_summary().get("operations") or [])
        self.assertEqual(n, len(r_all._iter_sale_blocks()))
        self.assertTrue(r_all._generate_xlsx_bytes())
        self.assertIn("RESUMEN GENERAL", self._html(r_all))

    def test_10_company_scope(self):
        self._complete_fixture()
        r = self._report()
        companies = {b["company"].id for b in r._iter_sale_blocks()}
        self.assertEqual(companies, {self.company.id})
        if self.other:
            r_other = self._report(
                company_id=self.other.id,
                company_ids=[(6, 0, [self.other.id])],
            )
            ids = {tx.company_id.id for b in r_other._iter_sale_blocks() for tx in b["txs"]}
            self.assertNotIn(self.company.id, ids)

    def test_11_currencies_dop_usd(self):
        r = self._report()
        dop_txt = r._format_amount(1000.0, self.dop)
        usd_txt = r._format_amount(1000.0, self.usd)
        self.assertTrue(dop_txt)
        self.assertTrue(usd_txt)
        self.assertNotEqual(dop_txt, usd_txt)
        if (self.dop.symbol or "") == "RD$":
            self.assertIn("RD$", dop_txt)
        if (self.usd.symbol or "") in ("$", "US$"):
            self.assertTrue("$" in usd_txt or "US$" in usd_txt)
            self.assertNotIn("RD$", usd_txt)

    def test_12_wizard_buttons(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_cost_vs_sale_report_form"
        )
        arch = view.arch_db or ""
        self.assertIn('name="action_preview"', arch)
        self.assertIn('string="Previsualizar"', arch)
        self.assertIn('name="action_download_pdf"', arch)
        self.assertIn('string="Descargar PDF"', arch)
        self.assertIn('name="action_download_xlsx"', arch)
        self.assertIn('string="Descargar Excel"', arch)
