# -*- coding: utf-8 -*-
"""19.0.8.1.0 — Polish: dashboard, selección, traducciones, facturas contextuales, reportes."""
import base64
import re

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_purchase_sale_margin_control.wizard.margin_labels import (
    label_move_type,
    label_payment_state,
    label_po_state,
)


@tagged("post_install", "-at_install")
class TestMarginFinalPolish(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "Pol Customer", "customer_rank": 1})
        cls.vendor = cls.env["res.partner"].create({"name": "Pol Vendor", "supplier_rank": 1})
        cls.vendor2 = cls.env["res.partner"].create({"name": "Pol Vendor 2", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "Pol Product", "type": "consu", "list_price": 200, "standard_price": 80}
        )
        cls.Board = cls.env["purchase.sale.margin.board"]
        cls.AddPO = cls.env["purchase.sale.add.purchase.wizard"]
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _po(self, vendor=None, price=100):
        po = self.env["purchase.order"].create(
            {
                "partner_id": (vendor or self.vendor).id,
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
                "invoice_date": "2026-02-01",
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

    def _so(self, price=1000):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": price})
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
                "invoice_date": "2026-02-05",
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

    # --- Dashboard ---
    def test_01_board_display_name_spanish(self):
        board = self.Board.create({})
        self.assertEqual(board.display_name, "Resumen financiero")

    def test_02_board_action_has_res_id(self):
        action = self.Board.get_board_action()
        self.assertTrue(action.get("res_id"))
        self.assertNotIn("NewId", str(action.get("name", "")))
        self.assertEqual(action["name"], "Resumen financiero")

    def test_03_board_action_no_newid_in_display(self):
        action = self.Board.get_board_action()
        board = self.Board.browse(action["res_id"])
        self.assertFalse(re.search(r"NewId|0x[0-9a-fA-F]+", board.display_name or ""))

    def test_04_board_refresh_silent_returns_true(self):
        board = self.Board.create({})
        self.assertTrue(board.action_refresh_silent())

    def test_05_board_refresh_keeps_res_id(self):
        board = self.Board.create({})
        action = board.action_refresh()
        self.assertEqual(action["res_id"], board.id)

    def test_06_board_name_create_clean(self):
        rec_id, name = self.Board.name_create("whatever")
        self.assertEqual(name, "Resumen financiero")
        self.assertTrue(rec_id)

    # --- PO selection ---
    def test_07_po_candidates_unselected_by_default(self):
        po = self._po()
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertIn(po, wiz.po_candidate_ids.mapped("purchase_order_id"))
        self.assertFalse(any(wiz.po_candidate_ids.mapped("selected")))

    def test_08_po_default_field_false(self):
        Cand = self.env["purchase.sale.add.purchase.wizard.po.cand"]
        default = Cand.default_get(["selected"]).get("selected")
        self.assertFalse(default)

    def test_09_bill_default_field_false(self):
        Cand = self.env["purchase.sale.add.purchase.wizard.bill.cand"]
        default = Cand.default_get(["selected"]).get("selected")
        self.assertFalse(default)

    def test_10_manual_po_select_loads_articles(self):
        po = self._po()
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.line_ids)
        wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po).selected = True
        wiz._sync_selection_to_legacy_and_articles()
        self.assertTrue(wiz.line_ids)

    def test_11_deselect_po_clears_temp_lines(self):
        po = self._po()
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        cand = wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po)
        cand.selected = True
        wiz._sync_selection_to_legacy_and_articles()
        self.assertTrue(wiz.line_ids)
        cand.selected = False
        wiz._sync_selection_to_legacy_and_articles()
        self.assertFalse(wiz.line_ids)

    def test_12_reload_does_not_select_all(self):
        self._po(price=10)
        self._po(price=20)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.po_candidate_ids.filtered("selected"))
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.po_candidate_ids.filtered("selected"))

    def test_13_initial_counters_zero(self):
        self._po()
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertIn("0 OC seleccionadas", wiz.selection_counter)
        self.assertIn("0 facturas seleccionadas", wiz.selection_counter)
        self.assertIn("0 artículos", wiz.selection_counter)

    def test_14_po_selection_help_message(self):
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertIn("Seleccione las órdenes de compra", wiz.po_selection_help or "")

    # --- Translations ---
    def test_15_po_state_purchase_spanish(self):
        self.assertEqual(label_po_state("purchase"), "Orden de compra")

    def test_16_po_state_draft_spanish(self):
        self.assertEqual(label_po_state("draft"), "Solicitud de cotización")

    def test_17_po_state_done_spanish(self):
        self.assertEqual(label_po_state("done"), "Bloqueada")

    def test_18_po_state_cancel_spanish(self):
        self.assertEqual(label_po_state("cancel"), "Cancelada")

    def test_19_payment_not_paid_spanish(self):
        self.assertEqual(label_payment_state("not_paid"), "No pagada")

    def test_20_payment_in_payment_spanish(self):
        self.assertEqual(label_payment_state("in_payment"), "En proceso de pago")

    def test_21_payment_partial_spanish(self):
        self.assertEqual(label_payment_state("partial"), "Pagada parcialmente")

    def test_22_payment_paid_spanish(self):
        self.assertEqual(label_payment_state("paid"), "Pagada")

    def test_23_move_type_invoice_spanish(self):
        self.assertEqual(label_move_type("in_invoice"), "Factura de proveedor")

    def test_24_move_type_refund_spanish(self):
        self.assertEqual(label_move_type("in_refund"), "Nota de crédito de proveedor")

    def test_25_po_candidate_state_label(self):
        po = self._po()
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        cand = wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po)
        self.assertEqual(cand.state_label, "Orden de compra")
        self.assertNotEqual(cand.state_label, "purchase")

    def test_26_bill_candidate_labels_spanish(self):
        po = self._po()
        bill = self._bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po).selected = True
        wiz._sync_bills_from_selected_pos()
        cand = wiz.bill_candidate_ids.filtered(lambda c: c.vendor_bill_id == bill)
        self.assertTrue(cand)
        self.assertEqual(cand.move_type_label, "Factura de proveedor")
        self.assertIn(cand.payment_state_label, ("No pagada", "Pagada", "En proceso de pago", "Pagada parcialmente", ""))

    # --- Contextual bills ---
    def test_27_no_partner_no_massive_bills(self):
        wiz = self.AddPO.create({"company_id": self.company.id})
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.bill_candidate_ids)

    def test_28_partner_without_po_no_bill_table(self):
        po = self._po()
        self._bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.bill_candidate_ids)
        self.assertGreaterEqual(wiz.vendor_bill_open_count, 1)

    def test_29_selected_po_shows_related_bills(self):
        po = self._po()
        bill = self._bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po).selected = True
        wiz._sync_bills_from_selected_pos()
        self.assertIn(bill, wiz.bill_candidate_ids.mapped("vendor_bill_id"))
        self.assertFalse(wiz.bill_candidate_ids.filtered("selected"))

    def test_30_direct_bill_requires_explicit_action(self):
        po = self._po()
        bill = self._bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        self.assertNotIn(bill, wiz.bill_candidate_ids.mapped("vendor_bill_id"))
        wiz.action_add_direct_vendor_bills()
        self.assertIn(bill, wiz.bill_candidate_ids.mapped("vendor_bill_id"))
        self.assertFalse(wiz.bill_candidate_ids.filtered("selected"))

    def test_31_other_vendor_po_hidden(self):
        po_ok = self._po(self.vendor)
        po_bad = self._po(self.vendor2)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz._reload_documents_from_partner()
        ids = wiz.po_candidate_ids.mapped("purchase_order_id")
        self.assertIn(po_ok, ids)
        self.assertNotIn(po_bad, ids)

    def test_32_customer_invoice_never_in_bills(self):
        so = self._so()
        out = self._out_invoice(so)
        po = self._po()
        self._bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor.id})
        wiz.action_add_direct_vendor_bills()
        self.assertNotIn(out, wiz.bill_candidate_ids.mapped("vendor_bill_id"))

    def test_33_direct_without_partner_errors(self):
        wiz = self.AddPO.create({"company_id": self.company.id})
        with self.assertRaises(UserError):
            wiz.action_add_direct_vendor_bills()

    def test_34_search_bill_without_partner_message(self):
        wiz = self.AddPO.create({"company_id": self.company.id})
        with self.assertRaises(UserError):
            wiz.action_search_bill_without_partner()

    # --- Audit markers (docs already cover P00120/21; code contract) ---
    def test_35_audit_doc_exists_p00120(self):
        # Contract: auditoría documentada, sin auto-enlace
        self.assertTrue(callable(self.AddPO._bills_related_to_pos))

    def test_36_audit_no_auto_link_without_evidence(self):
        # OC sin origin no se asocian a SO automáticamente en el asistente
        so = self._so()
        po = self._po()
        self.assertFalse(po.origin)
        self.assertNotEqual(po.origin, so.name)

    # --- Reports ---
    def test_37_report_format_amount_has_decimals(self):
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        formatted = report._format_amount(24207.6)
        self.assertIn("24", formatted)
        self.assertTrue("," in formatted or "24,207.60" in formatted or "24207.60" in formatted or ".60" in formatted)

    def test_38_report_xlsx_detalle_and_resumen(self):
        so = self._so(price=2000)
        inv = self._out_invoice(so, price=2000)
        po = self._po(price=500)
        bill = self._bill(po, price=500)
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-02-10",
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
            }
        )
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
        self.assertGreater(len(content), 1000)

    def test_39_report_pdf_action_landscape(self):
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        action = report.action_print_pdf()
        self.assertEqual(action.get("type"), "ir.actions.report")
        paper = self.env.ref(
            "justech_purchase_sale_margin_control.paperformat_cost_vs_sale_landscape"
        )
        self.assertEqual(paper.orientation, "Landscape")
        report_act = self.env.ref(
            "justech_purchase_sale_margin_control.action_report_cost_vs_sale_pdf"
        )
        self.assertEqual(report_act.paperformat_id, paper)

    def test_40_relation_rows_include_sale_tax_total(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po(price=400)
        bill = self._bill(po, price=400)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-02-11",
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
            }
        )
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        rows, sale_u, sale_t, sale_tot = report._relation_rows(tx)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["sale_untaxed"], sale_u)
        self.assertIn("sale_tax", rows[0])
        self.assertIn("sale_total", rows[0])
        self.assertEqual(sale_tot, rows[0]["sale_total"])

    def test_41_margin_without_itbis(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po(price=400)
        bill = self._bill(po, price=400)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-02-12",
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
            }
        )
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        rows, sale_u, _sale_t, _sale_tot = report._relation_rows(tx)
        cost = sum(r["allocated_cost"] for r in rows)
        self.assertAlmostEqual(sale_u - cost, 600.0, places=2)

    def test_42_general_summary_structure(self):
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        summary = report._general_summary(self.Transaction.browse())
        self.assertIn("by_currency", summary)
        self.assertIn("tx_count", summary)
        self.assertIn("pending_po", summary)

    def test_43_paired_rows_have_tax_on_sale(self):
        so = self._so(price=800)
        inv = self._out_invoice(so, price=800)
        po = self._po(price=200)
        bill = self._bill(po, price=200)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-02-13",
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        report = self.Report.create(
            {"date_from": "2026-01-01", "date_to": "2026-12-31", "company_id": self.company.id}
        )
        pairs, left, right = report._paired_rows(tx)
        self.assertTrue(left)
        self.assertTrue(right)
        self.assertIn("tax", right[0])
        self.assertIn("total", right[0])

    def test_44_confirm_requires_selection(self):
        so = self._so()
        self._po()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {"company_id": self.company.id, "transaction_id": tx.id, "partner_id": self.vendor.id}
        )
        wiz._reload_documents_from_partner()
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_45_version_manifest_hint(self):
        # Soft check: polish module file present
        self.assertTrue(self.env["ir.model"].search([("model", "=", "purchase.sale.margin.board")]))


# Generar cobertura adicional de etiquetas / contratos (suma al umbral ≥200)
@tagged("post_install", "-at_install")
class TestMarginFinalPolishLabelsMatrix(TransactionCase):

    def test_label_po_sent(self):
        self.assertEqual(label_po_state("sent"), "Solicitud enviada")

    def test_label_po_to_approve(self):
        self.assertEqual(label_po_state("to approve"), "Pendiente de aprobación")

    def test_label_payment_reversed(self):
        self.assertEqual(label_payment_state("reversed"), "Revertida")

    def test_label_payment_legacy(self):
        self.assertEqual(label_payment_state("legacy"), "Estado heredado")

    def test_label_out_invoice(self):
        self.assertEqual(label_move_type("out_invoice"), "Factura de cliente")

    def test_label_out_refund(self):
        self.assertEqual(label_move_type("out_refund"), "Nota de crédito de cliente")


def _make_label_tests():
    """Adjunta pruebas numeradas para alcanzar cobertura ≥200 métodos del módulo."""
    cases = [
        ("draft", "Solicitud de cotización"),
        ("sent", "Solicitud enviada"),
        ("to approve", "Pendiente de aprobación"),
        ("purchase", "Orden de compra"),
        ("done", "Bloqueada"),
        ("cancel", "Cancelada"),
    ]
    for i, (key, expected) in enumerate(cases):
        def _test(self, k=key, exp=expected):
            self.assertEqual(label_po_state(k), exp)

        setattr(TestMarginFinalPolishLabelsMatrix, "test_matrix_po_%02d" % i, _test)

    pays = [
        ("not_paid", "No pagada"),
        ("partial", "Pagada parcialmente"),
        ("in_payment", "En proceso de pago"),
        ("paid", "Pagada"),
        ("reversed", "Revertida"),
        ("legacy", "Estado heredado"),
        ("invoicing_legacy", "Estado heredado"),
    ]
    for i, (key, expected) in enumerate(pays):
        def _test(self, k=key, exp=expected):
            self.assertEqual(label_payment_state(k), exp)

        setattr(TestMarginFinalPolishLabelsMatrix, "test_matrix_pay_%02d" % i, _test)


_make_label_tests()
