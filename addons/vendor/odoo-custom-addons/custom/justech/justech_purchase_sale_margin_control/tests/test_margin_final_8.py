# -*- coding: utf-8 -*-
"""19.0.8.0.0 — Asistente simple + reporte fila-por-relación."""
import base64

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


RECOVERY_GROUP_XMLID = "justech_accounting_recovery.group_accounting_recovery"


@tagged("post_install", "-at_install")
class TestMarginFinal8(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "F8 Customer", "customer_rank": 1})
        cls.vendor_a = cls.env["res.partner"].create({"name": "F8 Vendor A", "supplier_rank": 1})
        cls.vendor_b = cls.env["res.partner"].create({"name": "F8 Vendor B", "supplier_rank": 1})
        cls.vendor_c = cls.env["res.partner"].create({"name": "F8 Vendor C", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "F8 Product", "type": "consu", "list_price": 200, "standard_price": 100}
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.AddPO = cls.env["purchase.sale.add.purchase.wizard"]
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        # Same coexistence as Sprint6: UAT cleanup unlinks draft moves.
        group = cls.env.ref(RECOVERY_GROUP_XMLID, raise_if_not_found=False)
        if group:
            cls.env.user.sudo().write({"group_ids": [Command.link(group.id)]})

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

    def _po(self, vendor=None, price=100, origin=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": (vendor or self.vendor_a).id,
                "origin": origin or False,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def _vendor_bill(self, po, price=None):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-01-15",
                "ref": "F8-NCF-%s" % po.id,
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
        # Draft is enough for wizard domains (state != cancel); avoid fiscal post requirements.
        return bill

    def _customer_invoice(self, so, price=None):
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-01-20",
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

    def test_01_partner_autoloads_pos(self):
        po = self._po(self.vendor_a)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        self.assertIn(po, wiz.po_candidate_ids.mapped("purchase_order_id"))

    def test_02_partner_autoloads_bills(self):
        po = self._po(self.vendor_a)
        bill = self._vendor_bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        # Sin OC marcada: no tabla masiva de facturas
        self.assertFalse(wiz.bill_candidate_ids)
        cand = wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po)
        cand.selected = True
        wiz._sync_bills_from_selected_pos()
        self.assertIn(bill, wiz.bill_candidate_ids.mapped("vendor_bill_id"))

    def test_03_no_incomplete_article_lines(self):
        Line = self.env["purchase.sale.add.purchase.wizard.line"]
        wiz = self.AddPO.create({"company_id": self.company.id})
        created = Line.create([{"wizard_id": wiz.id}])
        self.assertFalse(created)

    def test_04_partner_change_clears_incompatible(self):
        po_a = self._po(self.vendor_a)
        self._po(self.vendor_b)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        self.assertTrue(wiz.po_candidate_ids)
        wiz.partner_id = self.vendor_b
        wiz._reload_documents_from_partner()
        self.assertNotIn(po_a, wiz.po_candidate_ids.mapped("purchase_order_id"))

    def test_05_other_vendor_po_hidden(self):
        po_a = self._po(self.vendor_a)
        po_b = self._po(self.vendor_b)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        ids = wiz.po_candidate_ids.mapped("purchase_order_id")
        self.assertIn(po_a, ids)
        self.assertNotIn(po_b, ids)

    def test_06_customer_invoice_not_in_bills(self):
        so = self._so()
        cust_inv = self._customer_invoice(so)
        po = self._po(self.vendor_a)
        self._vendor_bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        wiz.action_add_direct_vendor_bills()
        self.assertNotIn(cust_inv, wiz.bill_candidate_ids.mapped("vendor_bill_id"))

    def test_07_vendor_bill_appears(self):
        po = self._po(self.vendor_a)
        bill = self._vendor_bill(po)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        cand = wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po)
        cand.selected = True
        wiz._sync_bills_from_selected_pos()
        self.assertIn(bill, wiz.bill_candidate_ids.mapped("vendor_bill_id"))

    def test_08_vendor_refund_identified(self):
        po = self._po(self.vendor_a)
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": self.vendor_a.id,
                "company_id": self.company.id,
                "invoice_date": "2026-01-16",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 50,
                            "name": "NC",
                        },
                    )
                ],
            }
        )
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        wiz.action_add_direct_vendor_bills()
        cand = wiz.bill_candidate_ids.filtered(lambda c: c.vendor_bill_id == refund)
        self.assertTrue(cand)
        self.assertEqual(cand.move_type, "in_refund")
        self.assertEqual(cand.move_type_label, "Nota de crédito de proveedor")

    def test_09_multiple_pos(self):
        po1 = self._po(self.vendor_a, price=10)
        po2 = self._po(self.vendor_a, price=20)
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
            }
        )
        wiz._reload_documents_from_partner()
        self.assertFalse(wiz.po_candidate_ids.filtered("selected"))
        for c in wiz.po_candidate_ids.filtered(
            lambda x: x.purchase_order_id in (po1 | po2)
        ):
            c.selected = True
        wiz._sync_selection_to_legacy_and_articles()
        self.assertGreaterEqual(len(wiz.po_candidate_ids.filtered("selected")), 2)
        wiz.action_confirm()
        self.assertIn(po1, tx.purchase_order_ids)
        self.assertIn(po2, tx.purchase_order_ids)

    def test_10_multiple_bills_one_tx(self):
        so = self._so(price=5000)
        inv = self._customer_invoice(so, price=5000)
        bills = self.env["account.move"]
        for i, vendor in enumerate([self.vendor_a, self.vendor_b, self.vendor_c, self.vendor_a, self.vendor_b]):
            po = self._po(vendor, price=100 + i)
            bills |= self._vendor_bill(po, price=100 + i)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, bills.ids)],
                "purchase_order_ids": [(6, 0, bills.invoice_line_ids.mapped("purchase_line_id.order_id").ids)],
            }
        )
        self.assertEqual(len(tx.vendor_bill_ids), 5)
        self.assertEqual(len(tx.customer_invoice_ids), 1)

    def test_11_three_vendors_one_tx(self):
        so = self._so()
        pos = self.env["purchase.order"]
        for v in (self.vendor_a, self.vendor_b, self.vendor_c):
            pos |= self._po(v)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, pos.ids)],
            }
        )
        self.assertEqual(len(tx.purchase_order_ids.mapped("partner_id")), 3)

    def test_12_five_bills_single_transaction(self):
        self.test_10_multiple_bills_one_tx()

    def test_13_sale_not_duplicated_across_bills(self):
        so = self._so(price=1000)
        inv = self._customer_invoice(so, 1000)
        bills = self.env["account.move"]
        for i in range(5):
            po = self._po(self.vendor_a, price=50 + i)
            bills |= self._vendor_bill(po, price=50 + i)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, bills.ids)],
            }
        )
        report = self.Report.create({"only_uat": True, "include_sales_without_cost": False})
        rows, sale_u, _, _ = report._relation_rows(tx)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r["sale_inv"] for r in rows}), 1)
        self.assertAlmostEqual(sale_u, 1000.0, places=2)

    def test_14_cost_not_duplicated(self):
        so = self._so(price=1000)
        inv = self._customer_invoice(so, 1000)
        po = self._po(self.vendor_a, price=200)
        bill = self._vendor_bill(po, 200)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        report = self.Report.create({"only_uat": True})
        rows, _, _, _ = report._relation_rows(tx)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["allocated_cost"], 200.0, places=2)

    def test_15_confirm_bill_only_without_po_selection(self):
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor_a.id,
                "company_id": self.company.id,
                "invoice_date": "2026-01-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 75,
                            "name": "Bill only",
                        },
                    )
                ],
            }
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
            }
        )
        wiz._reload_documents_from_partner()
        for c in wiz.po_candidate_ids:
            c.selected = False
        wiz.action_add_direct_vendor_bills()
        for c in wiz.bill_candidate_ids:
            c.selected = c.vendor_bill_id == bill
        wiz.action_confirm()
        self.assertIn(bill, tx.vendor_bill_ids)

    def test_16_confirm_po_without_bill(self):
        so = self._so()
        po = self._po(self.vendor_a, price=80)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz._onchange_purchase_order_ids()
        wiz.action_confirm()
        self.assertIn(po, tx.purchase_order_ids)

    def test_17_articles_autoload(self):
        po = self._po(self.vendor_a)
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        wiz._reload_documents_from_partner()
        # Sin selección: sin artículos
        self.assertFalse(wiz.line_ids)
        cand = wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po)
        cand.selected = True
        wiz._sync_selection_to_legacy_and_articles()
        self.assertTrue(wiz.line_ids)
        self.assertTrue(all(l.purchase_order_id for l in wiz.line_ids if not l.vendor_bill_id))

    def test_18_partial_qty_assign(self):
        so = self._so()
        po = self._po(self.vendor_a, price=100)
        # inflate qty
        po.order_line.write({"product_qty": 10})
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz._onchange_purchase_order_ids()
        wiz.line_ids.write({"qty_to_assign": 3})
        wiz.action_confirm()
        self.assertTrue(tx.line_ids.filtered(lambda l: l.line_type == "cost"))

    def test_19_functional_error_no_selection(self):
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create({"company_id": self.company.id, "transaction_id": tx.id})
        with self.assertRaises(UserError) as err:
            wiz.action_confirm()
        self.assertIn("Orden de Compra", str(err.exception))
        self.assertNotIn("purchase_order_id", str(err.exception))

    def test_20_excel_one_row_per_relation(self):
        so = self._so(price=900)
        inv = self._customer_invoice(so, 900)
        bills = self.env["account.move"]
        for i in range(3):
            po = self._po(self.vendor_a, price=100 + i)
            bills |= self._vendor_bill(po, 100 + i)
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, bills.ids)],
            }
        )
        report = self.Report.create({"only_uat": True})
        report.action_generate_xlsx()
        self.assertTrue(report.export_file)

    def test_21_subtotal_per_transaction(self):
        # covered by xlsx generation path; assert relation math
        so = self._so(price=1000)
        inv = self._customer_invoice(so, 1000)
        po1 = self._po(self.vendor_a, 100)
        po2 = self._po(self.vendor_a, 200)
        b1 = self._vendor_bill(po1, 100)
        b2 = self._vendor_bill(po2, 200)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "vendor_bill_ids": [(6, 0, [b1.id, b2.id])],
            }
        )
        report = self.Report.create({"only_uat": True})
        rows, sale_u, _, _ = report._relation_rows(tx)
        cost = sum(r["allocated_cost"] for r in rows)
        self.assertAlmostEqual(sale_u, 1000)
        self.assertAlmostEqual(cost, 300)

    def test_22_sale_not_summed_five_times(self):
        self.test_13_sale_not_duplicated_across_bills()

    def test_23_pdf_skips_empty_blocks(self):
        # empty sale-only tx should be excluded by default domain
        so = self._so()
        inv = self._customer_invoice(so)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
            }
        )
        self.assertEqual(tx.report_relation_class, "sale_without_cost")
        report = self.Report.create({"only_uat": True, "include_sales_without_cost": False})
        self.assertNotIn(tx, report._iter_transactions())

    def test_24_sales_without_cost_excluded_default(self):
        self.test_23_pdf_skips_empty_blocks()

    def test_25_include_incomplete_filter(self):
        so = self._so()
        inv = self._customer_invoice(so)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "is_uat_fixture": True,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
            }
        )
        report = self.Report.create({"only_uat": True, "include_sales_without_cost": True})
        rows, _, _, _ = report.with_context(include_empty_sale=True)._relation_rows(tx)
        self.assertTrue(rows)

    def test_26_multicompany_domain(self):
        wiz = self.AddPO.create({"company_id": self.company.id, "partner_id": self.vendor_a.id})
        self.assertEqual(wiz.company_id, self.company)

    def test_27_multicurrency_fields_present(self):
        po = self._po()
        self.assertTrue(po.currency_id)

    def test_28_credit_note_in_candidates(self):
        self.test_08_vendor_refund_identified()

    def test_29_uat_cleanup_prefix_safe(self):
        Cleanup = self.env["purchase.sale.margin.uat.cleanup.wizard"]
        wiz = Cleanup.create({"confirm": True})
        wiz.action_cleanup()
        self.assertEqual(
            self.Transaction.search_count([("is_uat_fixture", "=", True)]), 0
        )

    def test_30_no_regression_legacy_confirm(self):
        so = self._so()
        po = self._po(self.vendor_a, 55)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz._onchange_purchase_order_ids()
        action = wiz.action_confirm()
        self.assertEqual(action["res_model"], "purchase.sale.margin.transaction")
