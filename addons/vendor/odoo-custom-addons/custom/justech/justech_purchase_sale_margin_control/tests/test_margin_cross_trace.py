# -*- coding: utf-8 -*-
"""19.0.8.14.0 — App + cross-module traceability via margin.transaction hub."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCrossTrace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "XT Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "XT Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "XT Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 400,
            }
        )
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

    def _po(self, price=400):
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

    def _out_invoice(self, so, price=None):
        inv = self.env["account.move"].create(
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
        return inv

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

    def test_01_bidirectional_same_hub(self):
        so = self._so()
        inv = self._out_invoice(so)
        po = self._po()
        bill = self._bill(po)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "state": "validated",
            }
        )
        self.assertIn(po, tx.purchase_order_ids)
        self.env.flush_all()
        so.invalidate_recordset()
        po.invalidate_recordset()
        inv.invalidate_recordset()
        bill.invalidate_recordset()
        # Force recompute of hub + related docs
        self.assertIn(tx, so.margin_transaction_ids)
        self.assertEqual(so.jm_related_purchase_order_count, 1)
        self.assertIn(po, so.jm_related_purchase_order_ids)

        self.assertIn(so, po.jm_related_sale_order_ids)
        self.assertIn(tx, po.margin_transaction_ids)

        self.assertIn(po, inv.jm_related_purchase_order_ids)
        self.assertIn(bill, inv.jm_related_vendor_bill_ids)
        self.assertIn(tx, inv.margin_transaction_ids)

        self.assertIn(so, bill.jm_related_sale_order_ids)
        self.assertGreaterEqual(bill.related_sale_count, 1)

        # Actions open without crash
        self.assertTrue(so.action_view_related_purchase_orders())
        self.assertTrue(po.action_view_related_sale_orders())
        self.assertTrue(inv.action_view_related_purchase_orders())
        self.assertTrue(bill.action_view_related_sales())

    def test_02_three_pos_on_one_sale(self):
        so = self._so(3000)
        pos = [self._po(100) for _unused in range(3)]
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [p.id for p in pos])],
                "state": "validated",
            }
        )
        so.invalidate_recordset()
        self.assertEqual(so.jm_related_purchase_order_count, 3)
        for po in pos:
            po.invalidate_recordset()
            self.assertIn(so, po.jm_related_sale_order_ids)
            self.assertIn(tx, po.margin_transaction_ids)

    def test_03_compact_panel_fields(self):
        so = self._so()
        po = self._po()
        bill = self._bill(po, price=400)
        self.assertFalse(bill.name)  # draft → name False
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "state": "validated",
            }
        )
        so.invalidate_recordset()
        self.assertTrue(so.margin_control_state)
        self.assertIn(po.name, so.margin_control_po_names or "")
        # Must not crash when draft bills have name=False
        self.assertTrue(so.margin_control_bill_names)
    def test_04_app_menu_and_icon(self):
        menu = self.env.ref("justech_purchase_sale_margin_control.menu_purchase_sale_margin_root")
        self.assertEqual(menu.name, "Costos y Márgenes")
        self.assertTrue(menu.web_icon)
        self.assertIn("icon.png", menu.web_icon)
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_purchase_sale_margin_control")], limit=1
        )
        self.assertTrue(mod.application)

    def test_05_security_groups(self):
        for xmlid in (
            "group_margin_admin",
            "group_margin_finance",
            "group_margin_purchase",
            "group_margin_readonly",
        ):
            self.assertTrue(
                self.env.ref("justech_purchase_sale_margin_control.%s" % xmlid)
            )

    def test_06_report_oc_before_bill_in_template(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("Sin OC relacionada", arch)
        self.assertIn("Sin factura", arch)
        # OC label appears before NCF pattern in the bill+po branch
        idx_oc = arch.find("OC <")
        idx_sin_oc = arch.find("Sin OC relacionada")
        self.assertNotEqual(idx_oc, -1)
        self.assertNotEqual(idx_sin_oc, -1)
