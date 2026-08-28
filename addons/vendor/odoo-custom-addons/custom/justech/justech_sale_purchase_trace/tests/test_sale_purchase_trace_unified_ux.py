# -*- coding: utf-8 -*-
"""UX consolidation 19.0.1.2.3: generate PO + link existing, no auto-select."""
from uuid import uuid4

from lxml import etree
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTraceUnifiedUx(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Unified %s" % uuid4().hex[:6], "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor Unified A", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor Unified B", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Computadora Unified %s" % uuid4().hex[:6],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 1000,
                "standard_price": 600,
            }
        )

    def _so(self, qty=10, product=None, partner=None):
        product = product or self.product
        return self.env["sale.order"].create(
            {
                "partner_id": (partner or self.partner).id,
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
                            "description": sol.name,
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

    def _defaults(self, so):
        return (
            self.env["justech.buy.pending.wizard"]
            .with_context(active_id=so.id, default_sale_order_id=so.id)
            .default_get(["sale_order_id", "line_ids", "partner_id"])
        )

    def _set_stock(self, product, qty):
        wh = self.env["stock.warehouse"].search(
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

    def test_01_to_04_ten_six_four_block(self):
        so = self._so(10)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 6)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)
        self._buy(so, self.vendor_b, qty=4)
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)
        defaults = self._defaults(so)
        self.assertFalse(defaults.get("line_ids"))
        with self.assertRaises(ValidationError):
            self._buy(so, self.vendor_a, qty=1)

    def test_05_stock_plus_purchase_pending_three(self):
        so = self._so(10)
        if not self._set_stock(self.product, 2):
            self.skipTest("no warehouse")
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 2)
        self._buy(so, self.vendor_a, qty=5)
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 5)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 3)

    def test_06_split_six_plus_four(self):
        so = self._so(10)
        sol = so.order_line[0]
        po_a = self._buy(so, self.vendor_a, qty=6)
        po_b = self._buy(so, self.vendor_b, qty=4)
        sol = self._refresh(sol)
        self.assertEqual(po_a.order_line.sale_line_id, sol)
        self.assertEqual(po_b.order_line.sale_line_id, sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_07_cancel_releases_pending(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_cancel()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_08_partial_receipt_does_not_double_cover(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_confirm()
        po.order_line[0].write({"qty_received": 2})
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 6)
        self.assertAlmostEqual(sol.justech_qty_received, 2)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)

    def test_09_received_recalc_on_qty_change(self):
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

    def test_10_11_12_link_partial_full_over(self):
        so = self._so(10)
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(so.order_line[0])
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_b.id,
                "company_id": self.company.id,
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
        pol = po.order_line[0]
        wiz = (
            self.env["justech.link.existing.po.wizard"]
            .with_context(active_id=so.id, default_sale_order_id=so.id)
            .create({"sale_order_id": so.id})
        )
        match = wiz.line_ids.filtered(lambda l: l.purchase_order_id == po)
        self.assertTrue(match)
        self.assertAlmostEqual(match[:1].qty_to_assign, 4)
        match[:1].write({"selected": True, "qty_to_assign": 4})
        wiz.action_confirm_link()
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)
        with self.assertRaises(UserError):
            pol.justech_link_to_sale_line(sol, 1)

    def test_13_shared_po_two_sales(self):
        so_a = self._so(6)
        so_b = self._so(4)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
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
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so_a.order_line[0], 6)
        pol.justech_link_to_sale_line(so_b.order_line[0], 4)
        self.assertAlmostEqual(self._refresh(so_a.order_line[0]).justech_qty_purchased, 6)
        self.assertAlmostEqual(self._refresh(so_b.order_line[0]).justech_qty_purchased, 4)

    def test_14_billed_po_commercial_link_no_aml_write(self):
        so = self._so(4)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 4,
                            "price_unit": 500,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        aml_before = self.env["account.move.line"].search_count([])
        po.order_line[0].write({"qty_invoiced": 4})
        po.order_line[0].justech_link_to_sale_line(so.order_line[0], 4)
        aml_after = self.env["account.move.line"].search_count([])
        self.assertEqual(aml_before, aml_after)
        self.assertAlmostEqual(self._refresh(so.order_line[0]).justech_qty_purchased, 4)

    def test_15_16_invoice_via_sol_or_lonely(self):
        so = self._so(2)
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 2,
                            "price_unit": 1000,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )
        action = inv.action_justech_invoice_related_purchases()
        self.assertEqual(action.get("res_model"), "sale.order.line")
        lonely = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        lonely_action = lonely.action_justech_invoice_related_purchases()
        self.assertEqual(lonely_action.get("tag"), "display_notification")

    def test_17_concurrency_message(self):
        so = self._so(10)
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(so.order_line[0])
        wiz = self.env["justech.buy.pending.wizard"].create(
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
                            "qty_pending": 10,
                            "qty_to_buy": 4,
                            "selected": True,
                            "snapshot_pending": 10,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("cambiaron desde que abrió", str(err.exception).lower())

    def test_18_multicompany_vendor_blocked(self):
        other = self.env["res.company"].search(
            [("id", "!=", self.company.id)], limit=1
        )
        if not other:
            self.skipTest("no second company")
        vendor = self.env["res.partner"].create(
            {
                "name": "Vendor other co",
                "supplier_rank": 1,
                "company_id": other.id,
            }
        )
        so = self._so(2)
        with self.assertRaises(UserError):
            self._buy(so, vendor, qty=2)

    def test_19_multicurrency_po(self):
        usd = self.env.ref("base.USD")
        self.vendor_a.property_purchase_currency_id = usd
        so = self._so(2)
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.currency_id, usd)
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])

    def test_20_uom_preserved(self):
        so = self._so(3)
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.order_line.product_uom_id, so.order_line.product_uom_id)

    def test_21_22_stock_and_no_stock(self):
        so_empty = self._so(10)
        sol = self._refresh(so_empty.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_stock_covered, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)
        so_stock = self._so(10)
        if self._set_stock(self.product, 10):
            sol2 = self._refresh(so_stock.order_line[0])
            self.assertGreaterEqual(sol2.justech_qty_stock_covered, 0)

    def test_23_pending_zero_not_in_defaults(self):
        so = self._so(10)
        self._buy(so, self.vendor_a)
        defaults = self._defaults(so)
        self.assertFalse(defaults.get("line_ids"))

    def test_24_no_line_selected_message(self):
        so = self._so(10)
        sol = self._refresh(so.order_line[0])
        wiz = self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": self.vendor_a.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": sol.product_id.id,
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": 0,
                            "selected": False,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("seleccione", str(err.exception).lower())

    def test_25_vendor_required(self):
        so = self._so(2)
        sol = self._refresh(so.order_line[0])
        wiz = self.env["justech.buy.pending.wizard"].new(
            {
                "sale_order_id": so.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": sol.product_id.id,
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": 2,
                            "selected": True,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("proveedor", str(err.exception).lower())

    def test_26_default_get_does_not_auto_select(self):
        so = self._so(10)
        defaults = self._defaults(so)
        lines = defaults.get("line_ids") or []
        self.assertTrue(lines)
        for _cmd, _xid, vals in lines:
            self.assertFalse(vals.get("selected"))
            self.assertAlmostEqual(vals.get("qty_to_buy") or 0.0, 0.0)

    def test_generate_action_name_and_persist(self):
        so = self._so(2)
        action = so.action_justech_buy_pending()
        self.assertEqual(action.get("name"), "Generar orden de compra")
        self.assertEqual(action.get("res_model"), "justech.buy.pending.wizard")
        unsaved = self.env["sale.order"].new({"partner_id": self.partner.id})
        with self.assertRaises(UserError) as err:
            unsaved.action_justech_buy_pending()
        self.assertIn("Guarde la cotización", str(err.exception))

    def test_overbuy_message_includes_product(self):
        so = self._so(10)
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(so.order_line[0])
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
                                "qty_pending": 4,
                                "qty_to_buy": 6,
                                "selected": True,
                                "snapshot_pending": 4,
                            },
                        )
                    ],
                }
            )
        msg = str(err.exception)
        self.assertIn("6", msg)
        self.assertIn("4", msg)
        self.assertIn(self.product.name.split()[0], msg)

    def test_27_phantom_wizard_line_does_not_block(self):
        so = self._so(4)
        sol = self._refresh(so.order_line[0])
        wiz = self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": self.vendor_a.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (0, 0, {"selected": False}),
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": sol.product_id.id,
                            "description": sol.name,
                            "qty_sold": sol.justech_qty_sold,
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": 4,
                            "selected": True,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    ),
                ],
            }
        )
        action = wiz.action_create_purchase_order()
        self.assertTrue(action.get("res_id"))
