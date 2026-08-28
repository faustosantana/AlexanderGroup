# -*- coding: utf-8 -*-
"""19.0.1.2.6 — confirmed SO stock coverage + sold qty vs purchased integrity."""
from uuid import uuid4

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTrace126(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Trace 126 %s" % uuid4().hex[:6], "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor A Trace 126", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor B Trace 126", "supplier_rank": 1}
        )

    def _product(self, name=None):
        return self.env["product.product"].create(
            {
                "name": name or "Prod Trace 126 %s" % uuid4().hex[:8],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 100,
                "standard_price": 40,
            }
        )

    def _so(self, qty=10, product=None):
        product = product or self._product()
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

    def _refresh(self, sol):
        sol.invalidate_recordset()
        sol._compute_justech_purchase_coverage()
        return sol

    def _confirm(self, so):
        so.with_context(justech_approval_skip=True).action_confirm()
        if so.state not in ("sale", "done"):
            so.with_context(justech_approval_skip=True)._action_confirm()
        self.assertIn(so.state, ("sale", "done"))
        return so

    def _buy(self, so, vendor, qty=None):
        sol = self._refresh(so.order_line.filtered(lambda l: not l.display_type)[:1])
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

    def _po(self, product, qty, vendor=None):
        vendor = vendor or self.vendor_a
        return self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": qty,
                            "price_unit": product.standard_price,
                            "product_uom_id": product.uom_id.id,
                        },
                    )
                ],
            }
        )

    def _set_stock(self, product, qty, so=None):
        wh = (so and so.warehouse_id) or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if not wh:
            return False
        self.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": product.id,
                "location_id": wh.lot_stock_id.id,
                "inventory_quantity": qty,
            }
        ).action_apply_inventory()
        return True

    def test_confirmed_so_no_stock_pending_purchase_full_qty(self):
        product = self._product()
        so = self._so(10, product)
        self._confirm(so)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_confirmed_so_no_stock_generate_po(self):
        product = self._product()
        so = self._so(10, product)
        self._confirm(so)
        po = self._buy(so, self.vendor_a, qty=10)
        sol = self._refresh(so.order_line[0])
        self.assertEqual(po.origin, so.name)
        self.assertEqual(po.order_line.sale_line_id, sol)
        self.assertAlmostEqual(po.order_line.product_qty, 10)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_confirmed_so_no_stock_link_existing_po(self):
        product = self._product()
        so = self._so(10, product)
        self._confirm(so)
        po = self._po(product, 10)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 10)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_confirmed_so_partial_real_stock(self):
        product = self._product()
        so = self._so(10, product)
        if not self._set_stock(product, 4, so):
            self.skipTest("no warehouse")
        self._confirm(so)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 4)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6)

    def test_confirmed_so_full_real_stock(self):
        product = self._product()
        so = self._so(10, product)
        if not self._set_stock(product, 10, so):
            self.skipTest("no warehouse")
        self._confirm(so)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_outgoing_demand_not_treated_as_reserved_stock(self):
        product = self._product()
        so = self._so(10, product)
        self._confirm(so)
        sol = self._refresh(so.order_line[0])
        moves = sol.move_ids.filtered(
            lambda m: m.state not in ("cancel", "done")
            and m.location_dest_id.usage == "customer"
        )
        self.assertTrue(moves)
        demand = sum(moves.mapped("product_uom_qty"))
        actual = sum(moves.mapped("quantity"))
        self.assertAlmostEqual(demand, 10)
        self.assertAlmostEqual(actual, 0)
        self.assertAlmostEqual(sol._justech_reserved_stock_qty(), 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_so_qty_decrease_above_purchased_allowed(self):
        product = self._product()
        so = self._so(100, product)
        po = self._po(product, 70)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 70)
        so.order_line[0].write({"product_uom_qty": 80})
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.product_uom_qty, 80)
        self.assertAlmostEqual(sol.justech_qty_purchased, 70)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_so_qty_decrease_equal_purchased_allowed(self):
        product = self._product()
        so = self._so(100, product)
        po = self._po(product, 70)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 70)
        so.order_line[0].write({"product_uom_qty": 70})
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.product_uom_qty, 70)
        self.assertAlmostEqual(sol.justech_qty_purchased, 70)

    def test_so_qty_decrease_below_purchased_blocked(self):
        product = self._product()
        so = self._so(100, product)
        po = self._po(product, 70)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 70)
        with self.assertRaises(UserError) as err:
            so.order_line[0].write({"product_uom_qty": 69})
        self.assertIn("70", str(err.exception))
        self.assertIn("69", str(err.exception))
        self.assertIn("compradas o relacionadas", str(err.exception).lower())
        self.assertAlmostEqual(so.order_line[0].product_uom_qty, 100)

    def test_so_qty_decrease_cancelled_po_allowed(self):
        product = self._product()
        so = self._so(100, product)
        po = self._buy(so, self.vendor_a, qty=70)
        po.button_cancel()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 0)
        so.order_line[0].write({"product_uom_qty": 50})
        self.assertAlmostEqual(so.order_line[0].product_uom_qty, 50)

    def test_so_qty_decrease_partial_assignment(self):
        product = self._product()
        so = self._so(100, product)
        po = self._po(product, 100)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 40)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 40)
        so.order_line[0].write({"product_uom_qty": 50})
        so.order_line[0].write({"product_uom_qty": 40})
        with self.assertRaises(UserError):
            so.order_line[0].write({"product_uom_qty": 39})

    def test_so_qty_decrease_multiple_po(self):
        product = self._product()
        so = self._so(100, product)
        po1 = self._po(product, 40, self.vendor_a)
        po2 = self._po(product, 30, self.vendor_b)
        po1.order_line[0].justech_link_to_sale_line(so.order_line[0], 40)
        po2.order_line[0].justech_link_to_sale_line(so.order_line[0], 30)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 70)
        so.order_line[0].write({"product_uom_qty": 80})
        so.order_line[0].write({"product_uom_qty": 70})
        with self.assertRaises(UserError):
            so.order_line[0].write({"product_uom_qty": 60})

    def test_draft_so_qty_decrease_without_purchase_allowed(self):
        so = self._so(100)
        so.order_line[0].write({"product_uom_qty": 50})
        self.assertAlmostEqual(so.order_line[0].product_uom_qty, 50)

    def test_po_qty_decrease_recalculates_purchased(self):
        product = self._product()
        so = self._so(40, product)
        po = self._po(product, 40)
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 40)
        po.order_line[0].write({"product_qty": 20})
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 20)

    def test_stock_reserved_for_other_so_not_covering_this_line(self):
        product = self._product()
        if not self._set_stock(product, 4):
            self.skipTest("no warehouse")
        so_a = self._so(4, product)
        self._confirm(so_a)
        so_b = self._so(4, product)
        self._confirm(so_b)
        sol_b = self._refresh(so_b.order_line[0])
        self.assertAlmostEqual(sol_b.justech_qty_pending_purchase, 4)
        self.assertLessEqual(sol_b.justech_qty_stock_covered, 0.0001)
