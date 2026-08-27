# -*- coding: utf-8 -*-
"""19.0.7.0.0 — Exportación por transacción, unicidad factura, UAT."""
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


RECOVERY_GROUP_XMLID = "justech_accounting_recovery.group_accounting_recovery"


@tagged("post_install", "-at_install")
class TestMarginSprint6(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "S6 Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "S6 Vendor", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "S6 Product", "type": "consu", "list_price": 100, "standard_price": 40}
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        # UAT cleanup unlinks draft account.move. When justech_accounting_recovery
        # is installed (PROD clone), unlink requires Recuperación Contable.
        # Grant it to the test user only — no financial/SoD bypass in product code.
        cls._ensure_accounting_recovery_for_uat_cleanup()

    @classmethod
    def _ensure_accounting_recovery_for_uat_cleanup(cls):
        group = cls.env.ref(RECOVERY_GROUP_XMLID, raise_if_not_found=False)
        if not group:
            return
        cls.env.user.sudo().write({"group_ids": [Command.link(group.id)]})

    def _so(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 100})
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, origin=None, price=40):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "origin": origin or False,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def _bill(self, price=40, ref="S6-BILL"):
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        )
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "journal_id": journal.id,
                "ref": ref,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _invoice(self, price=100):
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def test_paired_rows_five_bills_one_invoice(self):
        so = self._so()
        bills = self.env["account.move"]
        for i in range(5):
            bills |= self._bill(price=10 + i, ref="S6-%s" % i)
        inv = self._invoice()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "vendor_bill_ids": [(6, 0, bills.ids)],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "is_uat_fixture": True,
            }
        )
        report = self.Report.create({})
        pairs, left, right = report._paired_rows(tx)
        self.assertEqual(len(left), 5)
        self.assertEqual(len(right), 1)
        self.assertEqual(len(pairs), 5)
        self.assertTrue(pairs[-1][2])

    def test_xlsx_groups_by_transaction(self):
        so = self._so()
        bill = self._bill()
        inv = self._invoice()
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "is_uat_fixture": True,
            }
        )
        report = self.Report.create({"only_uat": True})
        action = report.action_generate_xlsx()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertTrue(report.export_file)
        self.assertIn("detalle_costos_vs_ventas", report.export_filename)

    def test_vendor_bill_cannot_belong_to_two_transactions(self):
        bill = self._bill(ref="UNIQUE-BILL")
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "supplier_ids": [(6, 0, [self.vendor.id])],
            }
        )
        with self.assertRaises(ValidationError):
            self.Transaction.create(
                {
                    "company_id": self.company.id,
                    "vendor_bill_ids": [(6, 0, [bill.id])],
                    "supplier_ids": [(6, 0, [self.vendor.id])],
                }
            )

    def test_auto_link_multiple_po_same_transaction(self):
        so = self._so()
        po1 = self._po(origin=so.name, price=40)
        po2 = self._po(origin=so.name, price=50)
        txs = self.Transaction.search([("sale_order_ids", "in", so.id)])
        self.assertEqual(len(txs), 1)
        self.assertEqual(set(txs.purchase_order_ids.ids), {po1.id, po2.id})

    def test_pdf_action_exists(self):
        report = self.Report.create({})
        action = report.action_print_pdf()
        self.assertEqual(action["type"], "ir.actions.report")

    def test_uat_wizard_creates_six_cases(self):
        wiz = self.env["purchase.sale.margin.uat.wizard"].create(
            {"company_id": self.company.id}
        )
        wiz.action_generate_cases()
        self.assertGreaterEqual(len(wiz.created_transaction_ids), 6)
        self.assertTrue(all(wiz.created_transaction_ids.mapped("is_uat_fixture")))

    def test_uat_cleanup_removes_fixtures(self):
        wiz = self.env["purchase.sale.margin.uat.wizard"].create(
            {"company_id": self.company.id}
        )
        wiz.action_generate_cases()
        cleanup = self.env["purchase.sale.margin.uat.cleanup.wizard"].create({"confirm": True})
        cleanup.action_cleanup()
        remaining = self.Transaction.search_count([("is_uat_fixture", "=", True)])
        self.assertEqual(remaining, 0)

    def test_project_name_field(self):
        self.assertIn("project_name", self.Transaction._fields)
        self.assertIn("is_uat_fixture", self.Transaction._fields)

    def test_sale_without_cost_export_row(self):
        so = self._so()
        inv = self._invoice()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "is_uat_fixture": True,
            }
        )
        report = self.Report.create({})
        pairs, left, right = report._paired_rows(tx)
        self.assertFalse(left)
        self.assertEqual(len(right), 1)
        self.assertEqual(len(pairs), 1)

    def test_purchase_without_sale_shows_bill(self):
        po = self._po()
        bill = self._bill()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "supplier_ids": [(6, 0, [self.vendor.id])],
                "is_uat_fixture": True,
            }
        )
        report = self.Report.create({})
        pairs, left, right = report._paired_rows(tx)
        self.assertEqual(len(left), 1)
        self.assertFalse(right)
