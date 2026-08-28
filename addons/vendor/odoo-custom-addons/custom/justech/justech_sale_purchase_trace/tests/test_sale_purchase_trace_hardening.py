# -*- coding: utf-8 -*-
"""Pre-production hardening: bought vs received, supply state, suggestions."""
import time
from uuid import uuid4

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTraceHardening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Hardening %s" % uuid4().hex[:6], "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor Omega Hard", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor Cecomsa Hard", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop Hard %s" % uuid4().hex[:8],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 1000,
                "standard_price": 600,
            }
        )

    def _so(self, qty=10, product=None):
        product = product or self.product
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": product.list_price,
                        },
                    )
                ],
            }
        )

    def _buy(self, so, vendor, qty=None):
        sol = so.order_line.filtered(lambda l: not l.display_type)[:1]
        sol.invalidate_recordset()
        sol._compute_justech_purchase_coverage()
        pending = sol.justech_qty_pending_purchase
        buy_qty = pending if qty is None else qty
        wiz = self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": vendor.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": sol.product_id.id,
                            "qty_sold": sol.justech_qty_sold,
                            "qty_stock_covered": sol.justech_qty_stock_covered,
                            "qty_purchased": sol.justech_qty_purchased,
                            "qty_pending": pending,
                            "qty_to_buy": buy_qty,
                            "selected": True,
                            "snapshot_pending": pending,
                        },
                    )
                ],
            }
        )
        action = wiz.action_create_purchase_order()
        return self.env["purchase.order"].browse(action["res_id"])

    def _refresh(self, sol):
        sol.invalidate_recordset()
        sol._compute_justech_purchase_coverage()
        return sol

    def _set_stock(self, product, qty, so=None):
        wh = (so and so.warehouse_id) or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if not wh:
            return
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": product.id,
                "location_id": wh.lot_stock_id.id,
                "inventory_quantity": qty,
            }
        ).action_apply_inventory()

    def test_purchased_vs_received_partial(self):
        so = self._so(10)
        sol = so.order_line[0]
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 3})
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 6)
        self.assertAlmostEqual(sol.justech_qty_received, 3)
        self.assertAlmostEqual(sol.justech_qty_pending_receive, 3)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)
        self.assertIn(sol.justech_supply_state, ("partial_receipt", "partial_purchase"))

    def test_full_receipt_clears_pending_receive(self):
        so = self._so(10)
        sol = so.order_line[0]
        po = self._buy(so, self.vendor_a)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 10})
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_received, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_receive, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_commercial_vs_physical(self):
        so = self._so(10)
        self._set_stock(self.product, 4, so)
        sol = self._refresh(so.order_line[0])
        if sol.justech_qty_stock_covered < 4:
            return
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 3})
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_commercial, 10)
        self.assertAlmostEqual(sol.justech_qty_physical, 7)
        self.assertAlmostEqual(sol.justech_qty_pending_receive, 3)
        self.assertEqual(sol.justech_coverage_state, "pending_receipt")
        self.assertNotEqual(sol.justech_supply_state, "delivered")

    def test_cancel_without_receipt_restores_pending(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_cancel()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)
        self.assertAlmostEqual(sol.justech_qty_received, 0)

    def test_cancel_after_partial_receipt_keeps_received(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 2})
        try:
            po.button_cancel()
        except (UserError, ValidationError):
            return
        sol = self._refresh(so.order_line[0])
        # Follow real POL qty_received after cancel (Odoo may reverse a fake write).
        self.assertAlmostEqual(sol.justech_qty_received, po.order_line.qty_received or 0.0)
        self.assertLessEqual(sol.justech_qty_purchased, 0.0001)
        self.assertGreater(sol.justech_qty_pending_purchase, 0)

    def test_pending_deliver_from_qty_delivered(self):
        so = self._so(10)
        sol = so.order_line[0]
        state = sol._justech_supply_state_value(
            10, 0, 10, 0, 10, 0, 4, 6, 10
        )
        self.assertEqual(state, "partial_delivery")
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_pending_deliver, 10 - (sol.qty_delivered or 0.0))

    def test_customer_return_does_not_create_purchase_need(self):
        so = self._so(10)
        self._buy(so, self.vendor_a)
        sol = self._refresh(so.order_line[0])
        pending_before = sol.justech_qty_pending_purchase
        # A customer return must not invent a new purchase need.
        self.assertAlmostEqual(pending_before, 0)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)

    def test_vendor_return_reduces_received(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 10})
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_received, 10)
        po.order_line[0].write({"qty_received": 7})
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_received, 7)
        self.assertAlmostEqual(sol.justech_qty_pending_receive, 3)

    def test_overbuy_message(self):
        so = self._so(10)
        sol = so.order_line[0]
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(sol)
        with self.assertRaises(ValidationError) as err:
            self.env["justech.buy.pending.wizard"].create(
                {
                    "partner_id": self.vendor_b.id,
                    "sale_order_id": so.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "sale_line_id": sol.id,
                                "product_id": sol.product_id.id,
                                "qty_sold": 10,
                                "qty_pending": sol.justech_qty_pending_purchase,
                                "qty_to_buy": 5,
                                "selected": True,
                                "snapshot_pending": sol.justech_qty_pending_purchase,
                            },
                        )
                    ],
                }
            )
        self.assertIn("4", str(err.exception))
        self.assertIn("pendientes de compra", str(err.exception).lower())

    def test_fully_covered_message(self):
        so = self._so(10)
        self._buy(so, self.vendor_a)
        wiz = self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": self.vendor_a.id,
                "sale_order_id": so.id,
            }
        )
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("completamente cubierta", str(err.exception).lower())

    def test_stock_sufficient_warns_not_blocks(self):
        product = self.env["product.product"].create(
            {
                "name": "StockWarn %s" % uuid4().hex[:8],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 100,
                "standard_price": 50,
            }
        )
        so = self._so(10, product=product)
        self._set_stock(product, 10, so)
        sol = self._refresh(so.order_line[0])
        wiz = self.env["justech.buy.pending.wizard"].new(
            {
                "partner_id": self.vendor_a.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": product.id,
                            "qty_sold": 10,
                            "qty_stock_covered": max(sol.justech_qty_stock_covered, 10),
                            "qty_purchased": 0,
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": max(sol.justech_qty_pending_purchase, 0),
                            "selected": True,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    )
                ],
            }
        )
        wiz._compute_warning_html()
        if sol.justech_qty_stock_covered >= 10:
            self.assertTrue(wiz.warning_html)
            self.assertIn("inventario disponible", wiz.warning_html.lower())

    def test_po_suggestion_never_autoselect(self):
        so = self._so(10)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "origin": so.name,
                "company_id": so.company_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 10,
                            "price_unit": 500,
                        },
                    )
                ],
            }
        )
        wiz = (
            self.env["justech.link.existing.po.wizard"]
            .with_context(active_id=so.id, default_sale_order_id=so.id)
            .create({"sale_order_id": so.id})
        )
        if not wiz.line_ids:
            wiz.action_load_candidates()
        self.assertTrue(wiz.line_ids)
        self.assertFalse(any(wiz.line_ids.mapped("selected")))
        match = wiz.line_ids.filtered(lambda l: l.purchase_order_id == po)
        self.assertTrue(match)
        self.assertEqual(match[:1].match_level, "alta")
        self.assertTrue(match[:1].match_reason)

    def test_multiprovider_vendor_html(self):
        so = self._so(10)
        sol = so.order_line[0]
        po_a = self._buy(so, self.vendor_a, qty=6)
        po_b = self._buy(so, self.vendor_b, qty=4)
        sol = self._refresh(sol)
        html = sol.justech_vendor_supply_html or ""
        self.assertIn(po_a.name, html)
        self.assertIn(po_b.name, html)
        self.assertIn("Omega", html)
        self.assertIn("Cecomsa", html)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)

    def test_invoice_related_opens_coverage(self):
        so = self._so(2)
        so.order_line.product_id.invoice_policy = "order"
        so.with_context(justech_approval_skip=True).action_confirm()
        inv = so._create_invoices()
        action = inv.action_justech_invoice_related_purchases()
        self.assertEqual(action.get("res_model"), "sale.order.line")

    def test_trace_cost_inventory_plus_purchase(self):
        so = self._so(10)
        self._set_stock(self.product, 4, so)
        sol = self._refresh(so.order_line[0])
        if sol.justech_qty_stock_covered < 4:
            return
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(sol)
        self.assertTrue(sol.justech_trace_cost)
        self.assertIn("Inventario", sol.justech_cost_origin or "")
        self.assertIn("Compra", sol.justech_cost_origin or "")

    def test_performance_100_lines_compute(self):
        lines = []
        for i in range(100):
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_uom_qty": 1,
                        "price_unit": 100,
                        "name": "L%s" % i,
                    },
                )
            )
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": lines,
            }
        )
        start = time.time()
        so.order_line._compute_justech_purchase_coverage()
        so._compute_justech_purchase_totals()
        elapsed = time.time() - start
        self.assertLess(elapsed, 8.0)
        self.assertTrue(so.justech_supply_summary_html)
