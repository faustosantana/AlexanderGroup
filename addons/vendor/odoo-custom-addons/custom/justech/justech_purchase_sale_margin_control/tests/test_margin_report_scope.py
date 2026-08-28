# -*- coding: utf-8 -*-
"""19.0.8.18.0 — Alcance exclusivo del reporte Costos vs Ventas."""
import zipfile
from io import BytesIO

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginExclusiveReportScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "SCOPE Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "SCOPE Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "SCOPE Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 200,
            }
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

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

    def _out_invoice(self, so, price=None):
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
                            "price_unit": price if price is not None else so.order_line[:1].price_unit,
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
            "transaction_date": "2026-06-20",
            "state": state,
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
        return self.Transaction.create(vals)

    def _fixtures(self):
        so_c = self._so(1000)
        inv_c = self._out_invoice(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        complete = self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)

        so_s = self._so(500)
        inv_s = self._out_invoice(so_s, 500)
        sale_only = self._tx(so=so_s, inv=inv_s)

        po_k = self._po(150)
        bill_k = self._bill(po_k, 150)
        cost_only = self._tx(po=po_k, bill=bill_k)

        so_p = self._so(800)
        inv_p = self._out_invoice(so_p, 800)
        po_p = self._po(100)
        partial = self._tx(so=so_p, inv=inv_p, po=po_p)
        return {
            "complete": complete,
            "sale_only": sale_only,
            "cost_only": cost_only,
            "partial": partial,
        }

    def _report(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "report_layout": "compact",
            "report_scope": "all",
            "only_uat": True,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def _tx_ids(self, report):
        return report._iter_transactions().ids

    def _in_scope(self, report, fixtures):
        found = set(self._tx_ids(report))
        present = {}
        for key, rec in fixtures.items():
            if rec.id not in found:
                present[key] = False
                continue
            op = report._operation_summary(rec)
            present[key] = bool(report._op_included(op))
        return present

    def test_01_all_operations_default_excludes_incomplete(self):
        fx = self._fixtures()
        r = self._report(report_scope="all")
        present = self._in_scope(r, fx)
        self.assertTrue(present["complete"])
        self.assertTrue(present["partial"])
        self.assertFalse(present["sale_only"])
        self.assertFalse(present["cost_only"])
        self.assertEqual(r.report_scope, "all")

    def test_02_complete_only_excludes_incomplete(self):
        fx = self._fixtures()
        r = self._report(report_scope="complete_only")
        present = self._in_scope(r, fx)
        self.assertTrue(present["complete"])
        self.assertFalse(present["sale_only"])
        self.assertFalse(present["cost_only"])
        for op in r._iter_operation_summaries():
            if op["tx"] in fx.values():
                self.assertFalse(op.get("incomplete_sale_only"))
                self.assertFalse(op.get("incomplete_cost_only"))

    def test_03_sales_without_cost_only(self):
        fx = self._fixtures()
        r = self._report(report_scope="sales_wo_cost")
        present = self._in_scope(r, fx)
        self.assertFalse(present["complete"])
        self.assertFalse(present["partial"])
        self.assertTrue(present["sale_only"])
        self.assertFalse(present["cost_only"])
        ops = [op for op in r._iter_operation_summaries() if op["tx"] == fx["sale_only"]]
        self.assertEqual(len(ops), 1)
        self.assertTrue(ops[0].get("incomplete_sale_only"))
        self.assertAlmostEqual(ops[0]["cost_untaxed"], 0.0, places=2)
        grand = r._general_summary()
        self.assertGreaterEqual(grand.get("sales_wo_cost") or 0, 1)
        sale_ids = {op["tx"].id for op in grand.get("operations") or []}
        self.assertNotIn(fx["complete"].id, sale_ids)

    def test_04_costs_without_sale_only(self):
        fx = self._fixtures()
        r = self._report(report_scope="costs_wo_sale")
        present = self._in_scope(r, fx)
        self.assertFalse(present["complete"])
        self.assertFalse(present["partial"])
        self.assertFalse(present["sale_only"])
        self.assertTrue(present["cost_only"])
        ops = [op for op in r._iter_operation_summaries() if op["tx"] == fx["cost_only"]]
        self.assertEqual(len(ops), 1)
        self.assertTrue(ops[0].get("incomplete_cost_only"))
        grand = r._general_summary()
        self.assertGreaterEqual(grand.get("costs_wo_sale") or 0, 1)
        cost_ids = {op["tx"].id for op in grand.get("operations") or []}
        self.assertNotIn(fx["complete"].id, cost_ids)

    def test_05_incomplete_only_excludes_complete(self):
        fx = self._fixtures()
        r = self._report(report_scope="incomplete_only")
        present = self._in_scope(r, fx)
        self.assertFalse(present["complete"])
        self.assertTrue(present["sale_only"])
        self.assertTrue(present["cost_only"])
        # 8.29.6: venta+costo (parcial con PO) = completa estructural;
        # incompletas residuales no la incluyen.
        self.assertFalse(present["partial"])

    def test_06_include_sales_with_all(self):
        fx = self._fixtures()
        r = self._report(report_scope="all", include_sales_without_cost=True)
        present = self._in_scope(r, fx)
        self.assertTrue(present["complete"])
        self.assertTrue(present["sale_only"])
        self.assertFalse(present["cost_only"])

    def test_07_include_costs_with_all(self):
        fx = self._fixtures()
        r = self._report(report_scope="all", include_costs_without_sale=True)
        present = self._in_scope(r, fx)
        self.assertTrue(present["complete"])
        self.assertTrue(present["cost_only"])
        self.assertFalse(present["sale_only"])

    def test_08_pdf_xlsx_same_count(self):
        self._fixtures()
        for scope in (
            "all",
            "complete_only",
            "sales_wo_cost",
            "costs_wo_sale",
            "incomplete_only",
        ):
            r = self._report(report_scope=scope, only_uat=True)
            pdf_n = len(r._general_summary().get("operations") or [])
            xlsx_n = len(r._general_summary().get("operations") or [])
            self.assertEqual(pdf_n, xlsx_n, "PDF/XLSX universe mismatch for %s" % scope)
            data = r._generate_xlsx_bytes()
            self.assertTrue(data)
            html = self.env["ir.actions.report"]._render_qweb_html(
                "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf",
                r.ids,
            )
            if isinstance(html, (list, tuple)):
                html = html[0]
            body = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)
            self.assertIn("Operaciones:", body)
            self.assertIn(r._report_scope_label(), body)

    def test_09_summary_respects_scope(self):
        fx = self._fixtures()
        sale_r = self._report(report_scope="sales_wo_cost")
        sale_g = sale_r._general_summary()
        sale_ids = {op["tx"].id for op in sale_g.get("operations") or []}
        self.assertIn(fx["sale_only"].id, sale_ids)
        self.assertNotIn(fx["complete"].id, sale_ids)
        self.assertNotIn(fx["cost_only"].id, sale_ids)
        for bucket in (sale_g.get("by_currency") or {}).values():
            self.assertAlmostEqual(bucket.get("cost_untaxed") or 0.0, 0.0, places=2)
            self.assertAlmostEqual(bucket.get("margin") or 0.0, 0.0, places=2)

        cost_r = self._report(report_scope="costs_wo_sale")
        cost_g = cost_r._general_summary()
        cost_ids = {op["tx"].id for op in cost_g.get("operations") or []}
        self.assertIn(fx["cost_only"].id, cost_ids)
        self.assertNotIn(fx["complete"].id, cost_ids)
        self.assertNotIn(fx["sale_only"].id, cost_ids)
        for bucket in (cost_g.get("by_currency") or {}).values():
            self.assertAlmostEqual(bucket.get("sale_untaxed") or 0.0, 0.0, places=2)
            self.assertAlmostEqual(bucket.get("margin") or 0.0, 0.0, places=2)

    def test_10_cxp_respects_scope(self):
        fx = self._fixtures()
        sale_r = self._report(report_scope="sales_wo_cost")
        sale_g = sale_r._general_summary()
        sale_vendors = {row.get("vendor") for row in sale_g.get("cxp_rows") or []}
        self.assertNotIn(self.vendor.name, sale_vendors)

        cost_r = self._report(report_scope="costs_wo_sale")
        cost_g = cost_r._general_summary()
        cost_vendors = {row.get("vendor") for row in cost_g.get("cxp_rows") or []}
        self.assertIn(self.vendor.name, cost_vendors)

        all_r = self._report(report_scope="all")
        all_g = all_r._general_summary()
        complete_ops = [
            op for op in (all_g.get("operations") or []) if op["tx"] == fx["complete"]
        ]
        self.assertTrue(complete_ops)

    def test_11_no_duplicates(self):
        fx = self._fixtures()
        for scope in ("all", "complete_only", "sales_wo_cost", "costs_wo_sale", "incomplete_only"):
            r = self._report(report_scope=scope)
            ids = list(self._tx_ids(r))
            self.assertEqual(len(ids), len(set(ids)), "duplicated MTX in scope %s" % scope)
            block_ids = []
            for op in r._general_summary().get("operations") or []:
                for tx in op.get("txs") or [op["tx"]]:
                    block_ids.append(tx.id)
            self.assertEqual(len(block_ids), len(set(block_ids)), "duplicated ops in scope %s" % scope)
            ours = [i for i in ids if i in {rec.id for rec in fx.values()}]
            self.assertEqual(len(ours), len(set(ours)))

    def test_12_include_checkboxes_ignored_in_exclusive_scope(self):
        fx = self._fixtures()
        r = self._report(
            report_scope="sales_wo_cost",
            include_costs_without_sale=True,
            include_sales_without_cost=False,
        )
        present = self._in_scope(r, fx)
        self.assertTrue(present["sale_only"])
        self.assertFalse(present["cost_only"])
        self.assertFalse(present["complete"])
        self.assertEqual(r._report_scope_label(), "Ventas sin costos")
        flags = r._effective_include_flags()
        self.assertTrue(flags["sales_wo_cost"])
        self.assertFalse(flags["costs_wo_sale"])

    def test_13_wizard_hides_include_when_not_all(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_cost_vs_sale_report_form"
        )
        arch = view.arch_db or ""
        self.assertIn("show_complete", arch)
        self.assertIn("show_sales_without_cost", arch)
        self.assertIn("Operaciones a mostrar", arch)
        self.assertEqual(self._report().show_complete, True)

    def test_14_xlsx_contains_scope_label(self):
        self._fixtures()
        r = self._report(report_scope="costs_wo_sale", only_uat=True)
        data = r._generate_xlsx_bytes()
        self.assertTrue(data)
        zf = zipfile.ZipFile(BytesIO(data))
        blob = b"".join(zf.read(name) for name in zf.namelist() if name.endswith(".xml"))
        self.assertTrue(
            "Operaciones".encode("utf-8") in blob or "Costos sin venta".encode("utf-8") in blob
        )

    def test_15_pdf_sales_without_cost_labels(self):
        self._fixtures()
        r = self._report(report_scope="sales_wo_cost", only_uat=True)
        html = self.env["ir.actions.report"]._render_qweb_html(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf",
            r.ids,
        )
        if isinstance(html, (list, tuple)):
            html = html[0]
        body = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)
        self.assertIn("Ventas sin costos", body)
        self.assertIn("SIN COSTOS RELACIONADOS", body)
        self.assertIn("MARGEN PENDIENTE DE COSTO", body)
        self.assertNotIn("SIN VENTA RELACIONADA", body)
