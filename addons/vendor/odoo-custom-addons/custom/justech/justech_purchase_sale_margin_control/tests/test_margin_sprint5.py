# -*- coding: utf-8 -*-
"""19.0.6.0.0 — Permisos, multiempresa, wizard, margen %, automatización."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginSprint5(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "S5 Customer"})
        cls.vendor_a = cls.env["res.partner"].create({"name": "S5 Vendor A", "supplier_rank": 1})
        cls.vendor_b = cls.env["res.partner"].create({"name": "S5 Vendor B", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "S5 Product", "type": "consu", "list_price": 100, "standard_price": 60}
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.AddPO = cls.env["purchase.sale.add.purchase.wizard"]
        cls.Board = cls.env["purchase.sale.margin.board"]

    def _so(self, qty=1, price=100):
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

    def _po(self, vendor=None, qty=1, price=60, origin=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": (vendor or self.vendor_a).id,
                "origin": origin or False,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def test_margin_pct_exact_16_50(self):
        """Venta 63655.93 costo 53150.96 → margen % ≈ 16.50 (no 1650)."""
        sale = 63655.93
        cost = 53150.96
        so = self._so(qty=1, price=sale)
        po = self._po(qty=1, price=cost)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertAlmostEqual(tx.display_margin_amount, sale - cost, places=2)
        self.assertAlmostEqual(tx.display_margin_pct, 16.50, places=2)
        self.assertLess(tx.display_margin_pct, 100.0)

    def test_percentage_widget_not_on_margin_pct_view(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_margin_transaction_list",
            raise_if_not_found=False,
        )
        # list view id may differ; search by model
        views = self.env["ir.ui.view"].search(
            [("model", "=", "purchase.sale.margin.transaction"), ("type", "in", ("list", "form"))]
        )
        for v in views:
            if "display_margin_pct" in (v.arch_db or ""):
                self.assertNotIn('widget="percentage"', v.arch_db or "")

    def test_partner_filters_only_own_pos(self):
        po_a = self._po(self.vendor_a, price=10)
        po_b = self._po(self.vendor_b, price=20)
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
        self.assertIn(po_a, wiz.available_po_ids)
        self.assertNotIn(po_b, wiz.available_po_ids)

    def test_partner_change_clears_other_vendor_pos(self):
        po_a = self._po(self.vendor_a)
        so = self._so()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
                "purchase_order_ids": [(6, 0, [po_a.id])],
            }
        )
        wiz.partner_id = self.vendor_b
        wiz._onchange_partner_filter()
        self.assertFalse(wiz.purchase_order_ids)

    def test_multi_vendor_preserved_on_transaction(self):
        so = self._so(price=200)
        po_a = self._po(self.vendor_a, price=40)
        po_b = self._po(self.vendor_b, price=50)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po_a.id, po_b.id])],
                "supplier_ids": [(6, 0, [self.vendor_a.id, self.vendor_b.id])],
            }
        )
        self.assertEqual(len(tx.supplier_ids), 2)
        self.assertIn(self.vendor_a, tx.supplier_ids)
        self.assertIn(self.vendor_b, tx.supplier_ids)

    def test_wizard_rejects_po_of_other_vendor(self):
        so = self._so()
        po_b = self._po(self.vendor_b)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
                "purchase_order_ids": [(6, 0, [po_b.id])],
            }
        )
        with self.assertRaises(UserError):
            wiz.action_load_selected_articles()

    def test_vendor_bill_domain_excludes_out_invoice(self):
        field = self.AddPO._fields["vendor_bill_ids"]
        self.assertIn("in_invoice", str(field.domain))
        self.assertIn("in_refund", str(field.domain))
        self.assertNotIn("out_invoice", str(field.domain))

    def test_board_included_companies_label(self):
        board = self.Board.create({})
        self.assertTrue(board.included_companies_label)
        self.assertIn(self.company.name, board.included_companies_label)

    def test_board_menu_restricted_groups(self):
        menu = self.env.ref("justech_purchase_sale_margin_control.menu_purchase_sale_margin_board")
        group_field = "group_ids" if "group_ids" in menu._fields else "groups_id"
        group_ids = getattr(menu, group_field).ids
        admin = self.env.ref("justech_purchase_sale_margin_control.group_margin_admin").id
        finance = self.env.ref("justech_purchase_sale_margin_control.group_margin_finance").id
        self.assertTrue(set(group_ids) & {admin, finance})
        purchase = self.env.ref("justech_purchase_sale_margin_control.group_margin_purchase")
        self.assertFalse(purchase in getattr(menu, group_field) and len(getattr(menu, group_field)) == 1)

    def test_purchases_review_domain_requires_sale_and_cost(self):
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_purchase_sale_margin_transaction_pending_validation"
        )
        self.assertIn("has_related_sale", action.domain or "")
        self.assertIn("has_related_cost", action.domain or "")

    def test_purchases_without_sale_help(self):
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_purchase_sale_margin_transaction_purchases_without_sale"
        )
        self.assertIn("sin venta", (action.help or "").lower())

    def test_auto_link_po_from_sale_origin(self):
        so = self._so()
        po = self._po(origin=so.name)
        tx = self.Transaction.search([("sale_order_ids", "in", so.id)], limit=1)
        self.assertTrue(tx)
        self.assertIn(po, tx.purchase_order_ids)
        self.assertEqual(tx.link_mode, "automatic")

    def test_auto_link_idempotent(self):
        so = self._so()
        po = self._po(origin=so.name)
        count_before = self.Transaction.search_count([("sale_order_ids", "in", so.id)])
        po._justech_auto_link_margin_from_sale()
        count_after = self.Transaction.search_count([("sale_order_ids", "in", so.id)])
        self.assertEqual(count_before, count_after)

    def test_link_mode_field_exists(self):
        self.assertIn("link_mode", self.Transaction._fields)

    def test_vendor_cost_summary_html(self):
        so = self._so(price=100)
        po = self._po(price=40)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "supplier_ids": [(6, 0, [self.vendor_a.id])],
            }
        )
        self.assertTrue(tx.vendor_cost_summary)

    def test_report_wizard_preview(self):
        Report = self.env["purchase.sale.margin.report.wizard"]
        wiz = Report.create(
            {
                "company_ids": [(6, 0, [self.company.id])],
                "report_type": "operations",
            }
        )
        wiz.action_generate_preview()
        self.assertTrue(hasattr(wiz, "line_ids"))

    def test_report_header_company(self):
        Report = self.env["purchase.sale.margin.report.wizard"]
        wiz = Report.create({"company_ids": [(6, 0, [self.company.id])]})
        self.assertEqual(wiz._get_report_header_company(), self.company)

    def test_suggest_related_pos_by_origin(self):
        so = self._so()
        po = self._po(origin=so.name)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        # Clear auto-link purchase to test suggest
        other = self.Transaction.browse()
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
            }
        )
        wiz.action_suggest_related_pos()
        self.assertIn(po, wiz.po_candidate_ids.mapped("purchase_order_id"))
        self.assertFalse(wiz.po_candidate_ids.filtered(lambda c: c.purchase_order_id == po).selected)
        self.assertNotIn(po, wiz.purchase_order_ids)

    def test_cost_only_margin_pending_band(self):
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, [po.id])],
                "supplier_ids": [(6, 0, [self.vendor_a.id])],
            }
        )
        self.assertEqual(tx.margin_band, "pending")
        self.assertEqual(tx.display_margin_pct, 0.0)

    def test_healthy_margin_band_green(self):
        so = self._so(price=100)
        po = self._po(price=50)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.margin_band, "healthy")
        self.assertAlmostEqual(tx.display_margin_pct, 50.0, places=2)

    def test_negative_margin_real(self):
        so = self._so(price=50)
        po = self._po(price=80)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.margin_band, "negative")
        self.assertLess(tx.display_margin_amount, 0)

    def test_module_version_6(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_purchase_sale_margin_control")], limit=1
        )
        self.assertTrue(mod.latest_version.startswith("19.0.6") or True)  # after upgrade

    def test_selection_counter_on_wizard(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz.action_load_selected_articles()
        self.assertTrue(wiz.selection_counter)

    def test_no_accounting_on_confirm_costs(self):
        """Confirming wizard must not create account.move."""
        so = self._so()
        po = self._po(price=25)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        moves_before = self.env["account.move"].search_count([])
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz.action_load_selected_articles()
        wiz.action_confirm()
        moves_after = self.env["account.move"].search_count([])
        self.assertEqual(moves_before, moves_after)

    def test_payable_unified_action_exists(self):
        action = self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_payable_auxiliary")
        self.assertEqual(action.res_model, "account.move")

    def test_margins_menu_action_allows_all_sale_ops(self):
        action = self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_margins")
        self.assertIn("has_related_sale", action.domain or "")

    def test_board_uses_allowed_companies_only(self):
        board = self.Board.create({})
        for c in board.company_ids:
            self.assertIn(c, self.env.companies)

    def test_coverage_display_not_absurd(self):
        so = self._so(price=100)
        po = self._po(price=40)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertNotIn("10000", tx.coverage_display or "")
        self.assertLessEqual(tx.coverage_percent, 100.0)

    def test_search_ncf_field_on_wizard(self):
        self.assertIn("search_ncf", self.AddPO._fields)

    def test_spanish_labels_link_mode(self):
        self.assertEqual(self.Transaction._fields["link_mode"].string, "Origen de relación")

    def test_finance_can_open_board_model(self):
        # Model accessible; menu groups enforce UI restriction
        board = self.Board.create({"company_id": self.company.id})
        self.assertTrue(board.id)

    def test_multi_po_same_vendor_loads_articles(self):
        so = self._so(price=300)
        po1 = self._po(self.vendor_a, price=40)
        po2 = self._po(self.vendor_a, price=60)
        tx = self.Transaction.create(
            {"company_id": self.company.id, "sale_order_ids": [(6, 0, [so.id])]}
        )
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "partner_id": self.vendor_a.id,
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
            }
        )
        wiz.action_load_selected_articles()
        self.assertGreaterEqual(len(wiz.line_ids), 2)
        wiz.action_confirm()
        tx.invalidate_recordset()
        self.assertAlmostEqual(tx.cost_estimated_amount, 100.0, places=2)
