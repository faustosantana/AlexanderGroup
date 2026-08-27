# -*- coding: utf-8 -*-
"""19.0.8.29.22 — Gestionar compras hub + historical/manual cost (margins-only)."""
from odoo.tests import tagged, TransactionCase
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install", "justech_margin")
class TestManagePurchasesHub2922(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({"name": "Hub Customer 2922"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "LAVA PLATO LIMON 2922",
                "list_price": 100.0,
                "standard_price": 40.0,
                "type": "consu",
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so_with_qty(self, qty=30.0):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def test_01_invoice_manage_purchases_reuses_mtx(self):
        so = self._so_with_qty(30)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 30,
                            "price_unit": 100,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.write({"customer_invoice_ids": [(4, inv.id)]})
        act = inv.action_manage_purchases()
        self.assertEqual(act["res_model"], "purchase.sale.manage.purchases.wizard")
        wiz = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(**act["context"])
            .create({})
        )
        self.assertEqual(wiz.transaction_id, tx)
        # Second open still same MTX
        wiz2 = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(**act["context"])
            .create({})
        )
        self.assertEqual(wiz2.transaction_id, tx)
        self.assertEqual(
            self.Transaction.search_count(
                [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
            ),
            1,
        )

    def test_02_historical_cost_covers_pending_no_stock(self):
        so = self._so_with_qty(30)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        # Pretend 18 already via purchase assignment coverage path is empty → all pending
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "customer_id": self.customer.id,
            }
        )
        self.assertTrue(hub.line_ids)
        self.assertTrue(
            float_compare(hub.line_ids[0].pending_qty, 30.0, precision_digits=4) == 0
        )
        hist = self.env["purchase.sale.historical.cost.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "manage_wizard_id": hub.id,
            }
        )
        self.assertTrue(hist.line_ids)
        line = hist.line_ids[0]
        # Cover 12 historical after imagining 18 purchase — set qty 12 of 30
        line.write({"qty_to_cover": 12.0, "unit_cost": 35.0})
        # Leave other pending: first apply 12
        hist.action_apply()
        cost_lines = tx.line_ids.filtered(
            lambda l: l.line_type == "cost" and l.cost_source == "inventory"
        )
        self.assertEqual(len(cost_lines), 1)
        self.assertEqual(cost_lines.quantity, 12.0)
        self.assertEqual(cost_lines.amount_untaxed, 420.0)
        # No stock / accounting side effects
        self.assertFalse(cost_lines.stock_move_id)
        self.assertFalse(cost_lines.account_move_id)
        Quant = self.env["stock.quant"]
        q_before = Quant.search_count([("product_id", "=", self.product.id)])
        # Refresh coverage
        hub2 = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        self.assertTrue(
            float_compare(hub2.line_ids[0].historical_qty, 12.0, precision_digits=4)
            == 0
        )
        self.assertTrue(
            float_compare(hub2.line_ids[0].pending_qty, 18.0, precision_digits=4) == 0
        )
        self.assertEqual(
            Quant.search_count([("product_id", "=", self.product.id)]), q_before
        )

    def test_03_over_allocation_blocked(self):
        so = self._so_with_qty(10)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        hist = self.env["purchase.sale.historical.cost.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
            }
        )
        hist.line_ids[0].write({"qty_to_cover": 99.0, "unit_cost": 1.0})
        with self.assertRaises(Exception):
            hist.action_apply()

    def test_04_relate_existing_opens_canonical_engine(self):
        so = self._so_with_qty(5)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        act = hub.action_relate_existing_purchases()
        self.assertEqual(act["res_model"], "purchase.sale.create.transaction.wizard")
        self.assertEqual(act["name"], "Relacionar compras")

    def test_05_sale_first_hub_lists_sold_without_purchases(self):
        """29.25: hub shows sold lines even with 0 purchase / 0 ASG."""
        so = self._so_with_qty(30)
        p2 = self.env["product.product"].create(
            {"name": "ENVIO 2925", "list_price": 50, "type": "service"}
        )
        so.write(
            {
                "order_line": [
                    (0, 0, {"product_id": p2.id, "product_uom_qty": 1, "price_unit": 50})
                ]
            }
        )
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "customer_id": self.customer.id,
            }
        )
        self.assertEqual(len(hub.line_ids), 2)
        self.assertEqual(hub.demand_source, "sale_order")
        self.assertEqual(hub.pending_line_count, 2)
        self.assertTrue(hub.has_pending)
        self.assertEqual(hub.coverage_state, "none")
        act = hub.line_ids[0].action_manage_line()
        self.assertEqual(act["res_model"], "purchase.sale.manage.purchases.wizard")
        self.assertEqual(act["res_id"], hub.id)
        self.assertTrue(hub.active_line_id)

    def test_06_invoice_source_preferred_and_zero_amount_not_cover(self):
        so = self._so_with_qty(10)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 7,
                            "price_unit": 100,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.write({"customer_invoice_ids": [(4, inv.id)]})
        # Zero-amount "inventory" must NOT close pending
        self.env["purchase.sale.margin.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "line_type": "cost",
                "data_origin": "manual",
                "cost_source": "inventory",
                "sale_order_line_id": so.order_line.id,
                "sale_order_id": so.id,
                "product_id": self.product.id,
                "quantity": 7,
                "amount_untaxed": 0.0,
                "amount_total": 0.0,
                "is_manual": True,
            }
        )
        hub = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(active_model="account.move", active_id=inv.id)
            .create({})
        )
        self.assertEqual(hub.demand_source, "invoice")
        self.assertEqual(len(hub.line_ids), 1)
        self.assertTrue(
            float_compare(hub.line_ids.sold_qty, 7.0, precision_digits=4) == 0
        )
        self.assertTrue(
            float_compare(hub.line_ids.pending_qty, 7.0, precision_digits=4) == 0
        )

    def test_07_inline_po_partial_and_historical_complete(self):
        """29.26 CASE B: purchase 3 + historical 2 → complete on sold 5."""
        if "justech.purchase.sale.qty.assignment" not in self.env:
            self.skipTest("Trace qty.assignment required")
        so = self._so_with_qty(5)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        supplier = self.env["res.partner"].create(
            {"name": "UAT Inline Sup", "supplier_rank": 1}
        )
        po = self.env["purchase.order"].create(
            {
                "partner_id": supplier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 100,
                            "price_unit": 40,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        self.assertTrue(
            float_compare(hub.line_ids.pending_qty, 5.0, precision_digits=4) == 0
        )
        line = hub.line_ids[0]
        line.action_manage_line()
        line.action_set_panel_relate()
        line.supplier_id = supplier
        line.purchase_order_id = po
        line._onchange_purchase_order_id()
        self.assertTrue(line.pol_pick_ids)
        pick = line.pol_pick_ids.filtered(lambda p: p.product_id == self.product)[:1]
        pick.qty_to_use = 3.0
        line.action_apply_relate()
        hub._refresh_coverage()
        self.assertTrue(
            float_compare(hub.line_ids.purchase_qty, 3.0, precision_digits=4) == 0
        )
        self.assertTrue(
            float_compare(hub.line_ids.pending_qty, 2.0, precision_digits=4) == 0
        )
        # Residual PO available = 97
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        svc = LineAllocationService(self.env)
        self.assertTrue(
            float_compare(svc.pol_qty_available(po.order_line), 97.0, precision_digits=4)
            == 0
        )
        line = hub.line_ids[0]
        line.action_set_panel_historical()
        line.hist_qty = 2.0
        line.hist_unit_cost = 35.0
        line.action_apply_historical()
        hub._refresh_coverage()
        self.assertTrue(
            float_compare(hub.line_ids.pending_qty, 0.0, precision_digits=4) == 0
        )
        self.assertEqual(hub.line_ids.line_status, "complete")

    def test_08_new_po_excess_not_auto_assigned(self):
        """29.26 CASE E: buy 100 for pending 20 → ASG 20 only."""
        if "justech.purchase.sale.qty.assignment" not in self.env:
            self.skipTest("Trace qty.assignment required")
        so = self._so_with_qty(20)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        supplier = self.env["res.partner"].create(
            {"name": "UAT NewPO Sup", "supplier_rank": 1}
        )
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        line = hub.line_ids[0]
        line.action_set_panel_create_po()
        line.new_po_supplier_id = supplier
        line.new_po_qty = 100.0
        line.new_po_price = 40.0
        line.action_apply_create_po()
        hub._refresh_coverage()
        self.assertTrue(
            float_compare(hub.line_ids.purchase_qty, 20.0, precision_digits=4) == 0
        )
        self.assertTrue(
            float_compare(hub.line_ids.pending_qty, 0.0, precision_digits=4) == 0
        )
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        svc = LineAllocationService(self.env)
        po = tx.purchase_order_ids[:1]
        self.assertTrue(po)
        self.assertTrue(
            float_compare(svc.pol_qty_available(po.order_line), 80.0, precision_digits=4)
            == 0
        )

    def test_09_bulk_wizard_not_auto_opened(self):
        """29.26 CASE G: opening hub does not launch create_transaction wizard."""
        so = self._so_with_qty(5)
        act = so.action_manage_purchases()
        self.assertEqual(act["res_model"], "purchase.sale.manage.purchases.wizard")
        hub = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(**act["context"])
            .create({})
        )
        self.assertEqual(len(hub.line_ids), 1)
        # Bulk path still available as secondary
        bulk = hub.action_relate_existing_purchases()
        self.assertEqual(bulk["res_model"], "purchase.sale.create.transaction.wizard")
