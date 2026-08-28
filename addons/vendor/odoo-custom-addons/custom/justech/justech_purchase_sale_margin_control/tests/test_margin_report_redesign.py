# -*- coding: utf-8 -*-
"""19.0.8.2.0 — Rediseño financiero del reporte Costos vs Ventas."""
import base64

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginReportRedesign(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "RR Cliente INCABI", "customer_rank": 1})
        cls.vendor = cls.env["res.partner"].create({"name": "RR Proveedor", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "RR Product", "type": "consu", "list_price": 1000, "standard_price": 200}
        )
        cls.tax = cls.env["account.tax"].search(
            [("type_tax_use", "=", "sale"), ("company_id", "=", cls.company.id), ("amount", ">", 0)],
            limit=1,
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
                            "tax_ids": [(6, 0, self.tax.ids)] if self.tax else False,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _out_invoice(self, so, price=None, with_tax=True):
        taxes = self.tax.ids if (with_tax and self.tax) else []
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
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

    def _po(self, price=200):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": price})
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

    def _tx(self, so=None, inv=None, po=None, bill=None):
        vals = {
            "company_id": self.company.id,
            "transaction_date": "2026-03-05",
            "customer_id": self.customer.id,
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

    def test_01_paperformat_landscape(self):
        paper = self.env.ref(
            "justech_purchase_sale_margin_control.paperformat_cost_vs_sale_landscape"
        )
        self.assertEqual(paper.orientation, "Landscape")

    def test_02_report_uses_basic_layout_not_external(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("web.basic_layout", arch)
        self.assertNotIn("web.external_layout", arch)

    def test_03_title_in_template(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        self.assertIn("DETALLE DE COSTOS VS VENTAS", view.arch_db)

    def test_04_no_repeated_costos_venta_banner(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        # 8.8: Excel-style dual header once; no old per-op dual banners
        self.assertIn("COSTOS / PROVEEDORES", arch)
        self.assertIn("VENTA / CLIENTE", arch)
        self.assertEqual(arch.count("COSTOS / PROVEEDORES"), 1)
        self.assertEqual(arch.count("VENTA / CLIENTE"), 1)
        self.assertNotIn(">COSTOS RELACIONADOS<", arch)
        self.assertIn("SIN COSTOS RELACIONADOS", arch)
        self.assertNotIn("VENTA REALIZADA", arch)

    def test_05_customer_hierarchy_in_template(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        # 8.4: cliente en encabezado de venta gerencial
        self.assertIn("sale['customer']", view.arch_db)
        self.assertIn("jm-sale", view.arch_db)

    def test_06_margin_money_and_pct_in_template(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        self.assertNotIn("RESUMEN DE LA OPERACIÓN", view.arch_db)
        self.assertIn("op['margin']", view.arch_db)
        # 8.7: margin % via mpct = op.get('margin_pct') (color thresholds)
        self.assertTrue(
            "op['margin_pct']" in view.arch_db or "op.get('margin_pct')" in view.arch_db
        )
        self.assertIn("jm-margin-hero", view.arch_db)

    def test_07_margin_without_itbis(self):
        so = self._so(price=125280)
        inv = self._out_invoice(so, price=125280, with_tax=True)
        po = self._po(price=19440)
        bill = self._bill(po, price=19440)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        op = report._operation_summary(tx)
        # Margen = untaxed sale - untaxed cost (no usar totals con ITBIS)
        self.assertAlmostEqual(op["margin"], op["sale"]["untaxed"] - op["cost_untaxed"], places=2)
        self.assertNotEqual(op["margin"], op["sale"]["total"] - op["cost_total"])

    def test_08_sale_tax_from_invoice(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000, with_tax=True)
        po = self._po(price=200)
        bill = self._bill(po, price=200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        sale = report._sale_financials(tx)
        self.assertFalse(sale["is_estimated"])
        self.assertEqual(sale["document_kind"], "Factura de cliente")
        # Si hay impuesto configurado, amount_tax o fallback líneas
        if self.tax:
            self.assertGreater(abs(sale["tax"]), 0.0)
        self.assertAlmostEqual(sale["untaxed"], inv.amount_untaxed, places=2)
        self.assertAlmostEqual(sale["total"], inv.amount_total, places=2)

    def test_09_estimated_sale_not_as_invoice(self):
        so = self._so(price=500)
        po = self._po(price=100)
        bill = self._bill(po, price=100)
        tx = self._tx(so=so, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        sale = report._sale_financials(tx)
        self.assertTrue(sale["is_estimated"])
        self.assertIn("estimad", sale["invoice_label"].lower())
        self.assertNotIn("Factura de cliente", sale["document_kind"])

    def test_10_multiple_vendor_bills_one_sale(self):
        so = self._so(price=5000)
        inv = self._out_invoice(so, price=5000)
        bills = self.env["account.move"]
        pos = self.env["purchase.order"]
        for i in range(5):
            po = self._po(price=100 + i)
            pos |= po
            bills |= self._bill(po, price=100 + i)
        tx = self._tx(so=so, inv=inv)
        tx.write(
            {
                "purchase_order_ids": [(6, 0, pos.ids)],
                "vendor_bill_ids": [(6, 0, bills.ids)],
            }
        )
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        op = report._operation_summary(tx)
        self.assertEqual(len(op["costs"]), 5)
        # Venta no se multiplica
        self.assertAlmostEqual(op["sale"]["untaxed"], inv.amount_untaxed, places=2)
        self.assertAlmostEqual(op["margin"], op["sale"]["untaxed"] - op["cost_untaxed"], places=2)

    def test_11_customer_credit_note_sign(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "invoice_date": "2026-03-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "name": "NC",
                        },
                    )
                ],
            }
        )
        po = self._po(price=200)
        bill = self._bill(po, price=200)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        tx.write({"customer_invoice_ids": [(4, refund.id)]})
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        sale = report._sale_financials(tx)
        self.assertAlmostEqual(
            sale["untaxed"], inv.amount_untaxed - refund.amount_untaxed, places=2
        )

    def test_12_po_committed_without_bill(self):
        so = self._so(price=800)
        inv = self._out_invoice(so, price=800)
        po = self._po(price=300)
        tx = self._tx(so=so, inv=inv, po=po)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        costs = report._cost_rows(tx)
        self.assertTrue(costs)
        self.assertIn(costs[0]["kind"], ("po", "inventory"))
        label = (costs[0].get("payment_state") or costs[0].get("label") or "").lower()
        self.assertTrue(
            "pendiente" in label or "inventario" in label or "consumido" in label
        )
        self.assertNotIn("comprometido", label)

    def test_13_exempt_tax_label(self):
        so = self._so(price=500)
        inv = self._out_invoice(so, price=500, with_tax=False)
        po = self._po(price=100)
        bill = self._bill(po, price=100)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        sale = report._sale_financials(tx)
        if abs(sale["tax"]) < 0.0001:
            self.assertEqual(sale["tax_label"], "Exento")

    def test_14_format_amount_decimals(self):
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        formatted = report._format_amount(105840.0)
        self.assertTrue("105" in formatted)
        self.assertTrue("840" in formatted or "105,840" in formatted or "105840.00" in formatted)

    def test_15_general_summary_structure(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po(price=200)
        bill = self._bill(po, price=200)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        grand = report._general_summary()
        self.assertIn("by_currency_rows", grand)
        self.assertIn("top_clients", grand)
        self.assertIn("operations", grand)
        self.assertGreaterEqual(grand["tx_count"], 1)

    def test_16_xlsx_four_sheets(self):
        so = self._so(price=2000)
        inv = self._out_invoice(so, price=2000)
        po = self._po(price=400)
        bill = self._bill(po, price=400)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        report.action_generate_xlsx()
        self.assertTrue(report.export_file)
        content = base64.b64decode(report.export_file)
        # xlsx is zip — sheet names live in workbook.xml (may be compressed)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            wb = zf.read("xl/workbook.xml").decode("utf-8", errors="ignore")
        self.assertIn("Resumen", wb)
        self.assertIn("Operaciones", wb)
        self.assertIn("Detalle", wb)
        self.assertIn("Pendientes", wb)

    def test_17_margin_band_negative(self):
        so = self._so(price=100)
        inv = self._out_invoice(so, price=100, with_tax=False)
        po = self._po(price=500)
        bill = self._bill(po, price=500)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        op = report._operation_summary(tx)
        self.assertEqual(op["margin_band"], "negative")
        self.assertLess(op["margin"], 0)

    def test_18_pdf_action_bound_to_landscape(self):
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_report_cost_vs_sale_pdf"
        )
        paper = self.env.ref(
            "justech_purchase_sale_margin_control.paperformat_cost_vs_sale_landscape"
        )
        self.assertEqual(action.paperformat_id, paper)

    def test_19_footer_and_header_in_template(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db
        self.assertIn('class="header"', arch)
        self.assertIn('class="footer"', arch)
        self.assertTrue('class="page"' in arch or "class='page'" in arch)

    def test_20_relation_rows_compat(self):
        so = self._so(price=900)
        inv = self._out_invoice(so, price=900)
        po = self._po(price=150)
        bill = self._bill(po, price=150)
        tx = self._tx(so=so, inv=inv, po=po, bill=bill)
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        rows, sale_u, sale_t, sale_tot = report._relation_rows(tx)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["sale_untaxed"], sale_u)
        self.assertEqual(rows[0]["sale_tax"], sale_t)
        self.assertEqual(rows[0]["sale_total"], sale_tot)


# Cobertura adicional de contratos del rediseño
@tagged("post_install", "-at_install")
class TestMarginReportRedesignContracts(TransactionCase):

    def test_move_tax_helper_zero_without_move(self):
        from odoo.addons.justech_purchase_sale_margin_control.report.cost_vs_sale_financial import (
            _move_tax_amount,
        )

        self.assertEqual(_move_tax_amount(False), 0.0)

    def test_sign_refund(self):
        from odoo.addons.justech_purchase_sale_margin_control.report.cost_vs_sale_financial import (
            _sign_for_move,
        )

        Move = self.env["account.move"]
        refund = Move.new({"move_type": "out_refund"})
        self.assertEqual(_sign_for_move(refund), -1.0)
        inv = Move.new({"move_type": "out_invoice"})
        self.assertEqual(_sign_for_move(inv), 1.0)

    def test_state_labels_spanish(self):
        from odoo.addons.justech_purchase_sale_margin_control.report.cost_vs_sale_financial import (
            STATE_LABELS,
        )

        self.assertEqual(STATE_LABELS["approved"], "Aprobada")
        self.assertEqual(STATE_LABELS["pending_review"], "Pendiente de revisión")
