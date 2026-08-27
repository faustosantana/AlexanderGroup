# -*- coding: utf-8 -*-
"""19.0.1.2.7 — generate PO persists selected qty when OWL omits readonly fields."""
from uuid import uuid4

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTrace127(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Trace 127 %s" % uuid4().hex[:6], "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor A Trace 127", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor B Trace 127", "supplier_rank": 1}
        )

    def _product(self, name=None):
        return self.env["product.product"].create(
            {
                "name": name or "Prod Trace 127 %s" % uuid4().hex[:8],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 100,
                "standard_price": 40,
            }
        )

    def _so(self, qty=10, product=None, extra_lines=None):
        product = product or self._product()
        lines = [
            (
                0,
                0,
                {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "price_unit": product.list_price,
                },
            )
        ]
        if extra_lines:
            lines.extend(extra_lines)
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": lines,
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

    def _owl_payload_wiz(self, so, selections):
        """Create wizard as OWL does: selected/qty_to_buy only, no sale_line_id."""
        return self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": self.vendor_a.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (0, 0, {"selected": selected, "qty_to_buy": qty})
                    for selected, qty in selections
                ],
            }
        )

    def test_generate_po_selected_line_with_positive_qty(self):
        product = self._product()
        so = self._so(2, product)
        extra = self._product()
        so.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": extra.id,
                            "product_uom_qty": 6,
                            "price_unit": extra.list_price,
                        },
                    )
                ]
            }
        )
        wiz = self._owl_payload_wiz(so, [(True, 2.0), (False, 0.0)])
        self.assertFalse(wiz.line_ids[0].sale_line_id)
        action = wiz.action_create_purchase_order()
        po = self.env["purchase.order"].browse(action["res_id"])
        self.assertEqual(po.origin, so.name)
        self.assertEqual(po.partner_id, self.vendor_a)
        self.assertEqual(len(po.order_line), 1)
        self.assertAlmostEqual(po.order_line.product_qty, 2.0)
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 2.0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0.0)
        self.assertEqual(so.justech_purchase_count, 1)

    def test_generate_po_unselected_positive_qty_does_not_buy(self):
        so = self._so(2)
        wiz = self._owl_payload_wiz(so, [(False, 2.0)])
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("Seleccione al menos una línea", str(err.exception))
        self.assertFalse(self.env["purchase.order"].search([("origin", "=", so.name)]))

    def test_generate_po_incomplete_owl_payload_does_not_misbind(self):
        product = self._product("GEL-MISBIND")
        so = self._so(
            2,
            product,
            extra_lines=[
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": 6,
                        "price_unit": product.list_price,
                    },
                )
            ],
        )
        wiz = self._owl_payload_wiz(so, [(True, 2.0)])
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("Seleccione al menos una línea", str(err.exception))

    def test_generate_po_ignores_unselected_line(self):
        p1 = self._product("P1-127")
        p2 = self._product("P2-127")
        so = self._so(
            2,
            p1,
            extra_lines=[
                (
                    0,
                    0,
                    {
                        "product_id": p2.id,
                        "product_uom_qty": 6,
                        "price_unit": p2.list_price,
                    },
                )
            ],
        )
        wiz = self._owl_payload_wiz(so, [(True, 2.0), (False, 6.0)])
        po = self.env["purchase.order"].browse(
            wiz.action_create_purchase_order()["res_id"]
        )
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])
        self.assertAlmostEqual(self._refresh(so.order_line[1]).justech_qty_purchased, 0)

    def test_generate_po_zero_qty_blocked(self):
        so = self._so(2)
        wiz = self._owl_payload_wiz(so, [(True, 0.0)])
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("positiva", str(err.exception).lower())

    def test_generate_po_partial_qty(self):
        so = self._so(10)
        wiz = self._owl_payload_wiz(so, [(True, 4.0)])
        po = self.env["purchase.order"].browse(
            wiz.action_create_purchase_order()["res_id"]
        )
        self.assertAlmostEqual(po.order_line.product_qty, 4.0)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 4.0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6.0)

    def test_generate_po_multiple_selected_lines(self):
        p1 = self._product("PM1-127")
        p2 = self._product("PM2-127")
        so = self._so(
            2,
            p1,
            extra_lines=[
                (
                    0,
                    0,
                    {
                        "product_id": p2.id,
                        "product_uom_qty": 3,
                        "price_unit": p2.list_price,
                    },
                )
            ],
        )
        wiz = self._owl_payload_wiz(so, [(True, 2.0), (True, 3.0)])
        po = self.env["purchase.order"].browse(
            wiz.action_create_purchase_order()["res_id"]
        )
        self.assertEqual(len(po.order_line), 2)
        self.assertAlmostEqual(sum(po.order_line.mapped("product_qty")), 5.0)

    def test_generate_po_cjo_same_product_two_lines(self):
        """CJO-0000694 shape: two SOL same product, select qty 2 only."""
        product = self._product("GEL-127")
        so = self._so(
            2,
            product,
            extra_lines=[
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": 6,
                        "price_unit": product.list_price,
                    },
                )
            ],
        )
        wiz = self._owl_payload_wiz(so, [(True, 2.0), (False, 0.0)])
        po = self.env["purchase.order"].browse(
            wiz.action_create_purchase_order()["res_id"]
        )
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])
        self.assertAlmostEqual(po.order_line.product_qty, 2.0)
        self.assertAlmostEqual(self._refresh(so.order_line[0]).justech_qty_purchased, 2)
        self.assertAlmostEqual(self._refresh(so.order_line[1]).justech_qty_purchased, 0)

    def test_view_force_save_sale_line_id(self):
        view = self.env.ref(
            "justech_sale_purchase_trace.view_justech_buy_pending_wizard_form"
        )
        arch = view.arch_db or ""
        self.assertIn('name="sale_line_id"', arch)
        self.assertIn("force_save", arch)

    def test_126_no_stock_pending_still_holds(self):
        product = self._product()
        so = self._so(10, product)
        self._confirm(so)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)
        wiz = self._owl_payload_wiz(so, [(True, 10.0)])
        po = self.env["purchase.order"].browse(
            wiz.action_create_purchase_order()["res_id"]
        )
        self.assertAlmostEqual(po.order_line.product_qty, 10)

    def test_generate_po_does_not_duplicate_existing_purchased(self):
        so = self._so(10)
        self._owl_payload_wiz(so, [(True, 10.0)]).action_create_purchase_order()
        self.assertAlmostEqual(self._refresh(so.order_line[0]).justech_qty_pending_purchase, 0)
        wiz2 = self._owl_payload_wiz(so, [(True, 10.0)])
        with self.assertRaises(UserError) as err:
            wiz2.action_create_purchase_order()
        self.assertIn("completamente cubierta", str(err.exception).lower())

    def test_126_qty_below_purchased_still_blocked(self):
        product = self._product()
        so = self._so(100, product)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": 70,
                            "price_unit": product.standard_price,
                            "product_uom_id": product.uom_id.id,
                        },
                    )
                ],
            }
        )
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 70)
        with self.assertRaises(UserError):
            so.order_line[0].write({"product_uom_qty": 69})
        self.assertAlmostEqual(so.order_line[0].product_uom_qty, 100)
