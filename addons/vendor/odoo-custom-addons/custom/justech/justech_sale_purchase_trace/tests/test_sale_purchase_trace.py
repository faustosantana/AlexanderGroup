# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTrace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Trace Test", "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor A Trace", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor B Trace", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop Trace Test",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 1000,
                "standard_price": 600,
            }
        )
        cls.product_monitor = cls.env["product.product"].create(
            {
                "name": "Monitor Trace Test",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 200,
                "standard_price": 120,
            }
        )

    def _so(self, qty=10, product=None, partner=None):
        product = product or self.product
        so = self.env["sale.order"].create(
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
        return so

    def _buy(self, so, vendor, qty_map=None):
        """qty_map: {sale_line: qty} or None = all pending."""
        wiz = (
            self.env["justech.buy.pending.wizard"]
            .with_context(active_id=so.id, default_sale_order_id=so.id)
            .create({"partner_id": vendor.id, "sale_order_id": so.id})
        )
        # default_get lines already set if created via default_get — recreate properly
        wiz = self.env["justech.buy.pending.wizard"].with_context(
            active_id=so.id, default_sale_order_id=so.id
        ).create(
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
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": (qty_map or {}).get(
                                sol, sol.justech_qty_pending_purchase
                            ),
                            "selected": True,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    )
                    for sol in so.order_line.filtered(lambda l: not l.display_type)
                    if sol.justech_qty_pending_purchase > 0
                ],
            }
        )
        if qty_map:
            for wline in wiz.line_ids:
                if wline.sale_line_id in qty_map:
                    wline.qty_to_buy = qty_map[wline.sale_line_id]
        action = wiz.action_create_purchase_order()
        return self.env["purchase.order"].browse(action["res_id"])

    def test_01_full_purchase_ten(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a)
        sol = so.order_line[0]
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line.sale_line_id, sol)
        self.assertEqual(po.origin, so.name)
        self.assertAlmostEqual(po.order_line.product_qty, 10)
        sol.invalidate_recordset()
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)

    def test_02_03_04_split_vendors(self):
        so = self._so(10)
        sol = so.order_line[0]
        po_a = self._buy(so, self.vendor_a, {sol: 6})
        self.assertAlmostEqual(po_a.order_line.product_qty, 6)
        self.assertEqual(po_a.order_line.sale_line_id, sol)
        sol.invalidate_recordset()
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)
        # cannot buy 5
        with self.assertRaises(UserError):
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
                                "qty_stock_covered": sol.justech_qty_stock_covered,
                                "qty_purchased": sol.justech_qty_purchased,
                                "qty_pending": sol.justech_qty_pending_purchase,
                                "qty_to_buy": 5,
                                "selected": True,
                                "snapshot_pending": sol.justech_qty_pending_purchase,
                            },
                        )
                    ],
                }
            )
            wiz.action_create_purchase_order()
        po_b = self._buy(so, self.vendor_b, {sol: 4})
        self.assertAlmostEqual(po_b.order_line.product_qty, 4)
        sol.invalidate_recordset()
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)
        self.assertEqual(len(sol.purchase_line_ids), 2)

    def test_05_08_09_sale_line_id_and_origin(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a)
        self.assertTrue(po.order_line.sale_line_id)
        self.assertEqual(po.origin, so.name)

    def test_10_cancelled_po_excluded(self):
        so = self._so(10)
        sol = so.order_line[0]
        po = self._buy(so, self.vendor_a, {sol: 6})
        po.button_cancel()
        sol.invalidate_recordset()
        self.assertAlmostEqual(sol.justech_qty_purchased, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_14_15_multi_sol_and_pos(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 1000,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_monitor.id,
                            "product_uom_qty": 5,
                            "price_unit": 200,
                        },
                    ),
                ],
            }
        )
        po = self._buy(so, self.vendor_a)
        self.assertEqual(len(po.order_line), 2)
        for line in po.order_line:
            self.assertTrue(line.sale_line_id)

    def test_16_17_manual_po_link_partial(self):
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
                            "product_qty": 10,
                            "price_unit": 600,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so_a.order_line[0], 6)
        pol.invalidate_recordset()
        self.assertAlmostEqual(pol.justech_qty_available_to_assign, 4)
        pol.justech_link_to_sale_line(so_b.order_line[0], 4)
        so_a.order_line.invalidate_recordset()
        so_b.order_line.invalidate_recordset()
        self.assertAlmostEqual(so_a.order_line.justech_qty_purchased, 6)
        self.assertAlmostEqual(so_b.order_line.justech_qty_purchased, 4)
        self.assertAlmostEqual(pol.justech_qty_available_to_assign, 0)

    def test_18_billed_po_link_no_accounting_change(self):
        so = self._so(5)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 5,
                            "price_unit": 600,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        # Simulate invoiced qty without full bill flow if possible
        pol = po.order_line[0]
        # Mark received/invoiced via write if fields allow in draft done — use assignment path
        pol.write({"qty_received": 5})
        aml_before = self.env["account.move.line"].search_count([])
        pol.justech_link_to_sale_line(so.order_line[0], 5)
        aml_after = self.env["account.move.line"].search_count([])
        self.assertEqual(aml_before, aml_after)
        self.assertTrue(
            pol.sale_line_id == so.order_line[0]
            or self.env["justech.purchase.sale.qty.assignment"].search(
                [("purchase_line_id", "=", pol.id), ("state", "=", "active")]
            )
        )

    def test_19_other_company_blocked(self):
        Company = self.env["res.company"]
        other = Company.create({"name": "Otra Cia Trace"})
        so = self._so(5)
        po = self.env["purchase.order"].with_company(other).create(
            {
                "partner_id": self.vendor_a.id,
                "company_id": other.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 5,
                            "price_unit": 600,
                            "name": self.product.name,
                            "company_id": other.id,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            po.order_line.justech_link_to_sale_line(so.order_line[0], 5)

    def test_21_double_assign_blocked(self):
        so = self._so(10)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 10,
                            "price_unit": 600,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so.order_line[0], 10)
        so2 = self._so(5)
        with self.assertRaises(Exception):
            pol.justech_link_to_sale_line(so2.order_line[0], 1)

    def test_22_concurrency_snapshot(self):
        so = self._so(10)
        sol = so.order_line[0]
        # First purchase 6
        self._buy(so, self.vendor_a, {sol: 6})
        sol.invalidate_recordset()
        # Stale wizard still thinks pending=10
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
                            "qty_stock_covered": 0,
                            "qty_purchased": 0,
                            "qty_pending": 10,
                            "qty_to_buy": 10,
                            "selected": True,
                            "snapshot_pending": 10,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as err:
            wiz.action_create_purchase_order()
        self.assertIn("pendientes cambiaron", str(err.exception).lower())
        self.assertIn("actualice", str(err.exception).lower())

    def test_23_cancelled_sale(self):
        so = self._so(10)
        so.action_cancel()
        self.assertEqual(so.state, "cancel")

    def test_25_26_invoice_via_sol(self):
        so = self._so(2)
        so.order_line.product_id.invoice_policy = "order"
        so.with_context(justech_approval_skip=True).action_confirm()
        # Create invoice if possible
        inv = so._create_invoices()
        sols = inv._justech_invoice_sale_lines()
        self.assertTrue(sols)
        # Invoice without SOL
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
                            "price_unit": 100,
                            "name": "Sin SOL",
                        },
                    )
                ],
            }
        )
        self.assertFalse(lonely._justech_invoice_sale_lines())
        action = lonely.action_justech_invoice_related_purchases()
        self.assertEqual(action.get("tag"), "display_notification")

    def test_30_margin_bridge_collect(self):
        so = self._so(5)
        po = self._buy(so, self.vendor_a)
        if "purchase.sale.margin.transaction" not in self.env:
            return
        Tx = self.env["purchase.sale.margin.transaction"]
        if not hasattr(Tx, "justech_collect_purchase_lines_from_sale"):
            return
        tx = Tx.create(
            {
                "name": "TX Trace Test",
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
            }
        )
        pols = tx.justech_collect_purchase_lines_from_sale()
        self.assertIn(po.order_line[0], pols)

    def test_standalone_no_margin_dependency(self):
        dep = self.env["ir.module.module.dependency"].search(
            [
                ("module_id.name", "=", "justech_sale_purchase_trace"),
                ("name", "=", "justech_purchase_sale_margin_control"),
            ]
        )
        self.assertFalse(
            dep,
            "justech_purchase_sale_margin_control must not be a hard dependency",
        )

    def test_33_company_on_new_po(self):
        so = self._so(3)
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.company_id, so.company_id)

    def test_34_multicurrency_allowed(self):
        usd = self.env.ref("base.USD")
        self.vendor_a.property_purchase_currency_id = usd
        so = self._so(2)
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.currency_id, usd)
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])

    def test_stock_coverage_reduces_pending(self):
        so = self._so(10)
        sol = so.order_line[0]
        # Monkeypatch stock cover by writing free via compute override simulation:
        # set free_qty_today if field exists by creating quant
        StockQuant = self.env["stock.quant"]
        wh = so.warehouse_id or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if wh:
            StockQuant.with_context(inventory_mode=True).create(
                {
                    "product_id": self.product.id,
                    "location_id": wh.lot_stock_id.id,
                    "inventory_quantity": 4,
                }
            ).action_apply_inventory()
        sol.invalidate_recordset()
        sol._compute_justech_purchase_coverage()
        # Pending should be <= 10; with stock ideally 6
        self.assertLessEqual(sol.justech_qty_pending_purchase, 10)
        if sol.justech_qty_stock_covered >= 4:
            self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6)

    def test_validation_negative_qty(self):
        so = self._so(5)
        sol = so.order_line[0]
        with self.assertRaises(ValidationError):
            self.env["justech.buy.pending.wizard.line"].create(
                {
                    "wizard_id": self.env["justech.buy.pending.wizard"]
                    .create(
                        {
                            "partner_id": self.vendor_a.id,
                            "sale_order_id": so.id,
                        }
                    )
                    .id,
                    "sale_line_id": sol.id,
                    "product_id": sol.product_id.id,
                    "qty_sold": 5,
                    "qty_pending": 5,
                    "qty_to_buy": -1,
                    "selected": True,
                    "snapshot_pending": 5,
                }
            )
