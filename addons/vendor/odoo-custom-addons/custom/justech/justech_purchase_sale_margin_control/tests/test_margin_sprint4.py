# -*- coding: utf-8 -*-
"""19.0.5.0.0 — Fórmulas, próxima acción, wizard proveedor, márgenes."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginSprint4(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "S4 Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "S4 Vendor", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {
                "name": "S4 Product",
                "type": "consu",
                "list_price": 231.6098,
                "standard_price": 135.0,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.AddPO = cls.env["purchase.sale.add.purchase.wizard"]

    def _so(self, qty=100.0, price=231.6098):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": qty, "price_unit": price})
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, qty=100.0, price=135.0):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def test_margin_formula_sale_23160_cost_13500(self):
        so = self._so(qty=100, price=231.6098)
        po = self._po(qty=100, price=135.0)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": so.partner_id.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertAlmostEqual(tx.display_sale_amount, 23160.98, places=2)
        self.assertAlmostEqual(tx.display_cost_amount, 13500.0, places=2)
        self.assertAlmostEqual(tx.display_margin_amount, 9660.98, places=2)
        self.assertAlmostEqual(tx.display_margin_pct, 41.71, places=2)
        self.assertNotEqual(tx.display_margin_amount, -13500.0)
        self.assertLessEqual(tx.coverage_percent, 100.0)

    def test_cost_only_not_negative_margin(self):
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, [po.id])],
                "supplier_ids": [(6, 0, [self.vendor.id])],
            }
        )
        self.assertFalse(tx.has_related_sale)
        self.assertEqual(tx.display_margin_amount, 0.0)
        self.assertEqual(tx.margin_band, "pending")

    def test_sale_without_cost_margin_pending(self):
        so = self._so()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_id": so.partner_id.id,
            }
        )
        self.assertTrue(tx.sale_without_cost)
        self.assertEqual(tx.margin_band, "pending")
        self.assertEqual(tx.next_action, "add_costs")

    def test_coverage_never_10000(self):
        so = self._so(qty=1, price=100)
        po = self._po(qty=1, price=50)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertLessEqual(tx.coverage_percent, 100.0)
        self.assertEqual(tx.coverage_display, "Pendiente")

    def test_wizard_requires_partner_then_po(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
            }
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor.id,
            }
        )
        self.assertIn(po, wiz.available_po_ids)
        with self.assertRaises(UserError):
            wiz.action_load_selected_articles()
        wiz.purchase_order_ids = [(6, 0, [po.id])]
        wiz.action_load_selected_articles()
        self.assertTrue(wiz.line_ids)

    def test_vendor_bill_domain_excludes_customer_invoices(self):
        # Domain enforced on the form view for vendor_bill_ids
        view = self.env.ref("justech_purchase_sale_margin_control.view_purchase_sale_margin_transaction_form")
        self.assertIn("in_invoice", view.arch_db)
        self.assertIn("in_refund", view.arch_db)
        self.assertNotIn("'out_invoice'", view.arch_db)

    def test_margins_action_exists(self):
        self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_margins")

    def test_next_action_finance_pending(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "validated",
                "validation_state": "validated",
            }
        )
        self.assertEqual(tx.next_action, "approve_finance")

    def test_healthy_margin_band(self):
        so = self._so(qty=1, price=200)
        po = self._po(qty=1, price=100)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.margin_band, "healthy")

    def test_negative_margin_band(self):
        so = self._so(qty=1, price=50)
        po = self._po(qty=1, price=100)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.margin_band, "negative")
        self.assertLess(tx.display_margin_amount, 0)

    def test_add_vendor_bills_action(self):
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        action = tx.action_add_vendor_bills()
        self.assertEqual(action["res_model"], "purchase.sale.add.purchase.wizard")

    def test_board_net_cash_flow_field(self):
        board = self.env["purchase.sale.margin.board"].create({})
        self.assertTrue(hasattr(board, "net_cash_flow"))

    def test_spanish_next_action_label(self):
        self.assertEqual(self.Transaction._fields["next_action"].string, "Próxima acción")

    def test_multi_po_via_partner_wizard(self):
        so = self._so(qty=1, price=200)
        po1 = self._po(qty=1, price=40)
        po2 = self._po(qty=1, price=60)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor.id,
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
            }
        )
        wiz.action_load_selected_articles()
        wiz.action_confirm()
        tx.invalidate_recordset()
        self.assertAlmostEqual(tx.cost_estimated_amount, 100.0, places=2)

    def test_http_smoke_module_installed(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_purchase_sale_margin_control")], limit=1
        )
        self.assertEqual(mod.state, "installed")
        self.assertTrue(bool(mod.latest_version))

    def test_low_margin_band(self):
        so = self._so(qty=1, price=100)
        po = self._po(qty=1, price=90)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.margin_band, "low")

    def test_suggest_related_pos(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor.id,
            }
        )
        wiz.action_suggest_related_pos()
        # Sugerencia: OC aparece en candidatos, sin preselección automática
        self.assertIn(po, wiz.po_candidate_ids.mapped("purchase_order_id"))
        self.assertNotIn(po, wiz.po_candidate_ids.filtered("selected").mapped("purchase_order_id"))
        self.assertNotIn(po, wiz.purchase_order_ids)

    def test_closed_next_action(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "closed",
            }
        )
        self.assertEqual(tx.next_action, "closed")

    def test_ready_to_close_next_action(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "approved",
                "validation_state": "validated",
                "approval_state": "approved",
            }
        )
        self.assertEqual(tx.next_action, "ready_to_close")

    def test_validate_relation_next_action(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "pending_review",
            }
        )
        self.assertEqual(tx.next_action, "validate_relation")

    def test_coverage_display_no_cost(self):
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        self.assertEqual(tx.coverage_display, "No disponible")

    def test_board_has_compact_kpis(self):
        board = self.env["purchase.sale.margin.board"].create({})
        board.action_refresh()
        for fname in (
            "total_sales_amount",
            "related_costs_amount",
            "confirmed_real_margin",
            "amount_to_collect_total",
            "amount_to_pay_total",
            "net_cash_flow",
            "sales_without_cost_count",
            "purchases_without_sale_count",
            "pending_validation_count",
            "pending_approval_count",
            "negative_margin_count",
        ):
            self.assertTrue(hasattr(board, fname), fname)

    def test_menus_margins_and_payable(self):
        self.env.ref("justech_purchase_sale_margin_control.menu_purchase_sale_margins")
        self.env.ref("justech_purchase_sale_margin_control.menu_purchase_sale_payable_auxiliary_root")

    def test_real_margin_uses_estimated_sale_when_no_invoice(self):
        so = self._so(qty=10, price=100)
        po = self._po(qty=10, price=40)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        # No customer invoice → sale_real may be 0; display margin still healthy
        self.assertGreater(tx.display_margin_amount, 0)
        self.assertAlmostEqual(tx.display_margin_amount, 600.0, places=2)

    def test_partner_filters_available_pos(self):
        po = self._po()
        other_vendor = self.env["res.partner"].create({"name": "Other Vend", "supplier_rank": 1})
        po2 = self.env["purchase.order"].create(
            {
                "partner_id": other_vendor.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": 10})
                ],
            }
        )
        po2.button_confirm()
        wiz = self.AddPO.create(
            {"company_id": self.company.id, "partner_id": self.vendor.id}
        )
        self.assertIn(po, wiz.available_po_ids)
        self.assertNotIn(po2, wiz.available_po_ids)
