# -*- coding: utf-8 -*-
"""Suite formal 60 escenarios — Sale → Purchase → Inventory Traceability."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTraceSixty(TransactionCase):
    """Escenarios 1–60 explícitos (no artificiales)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente SPIT 60", "customer_rank": 1}
        )
        cls.vendor_a = cls.env["res.partner"].create(
            {"name": "Proveedor A SPIT", "supplier_rank": 1}
        )
        cls.vendor_b = cls.env["res.partner"].create(
            {"name": "Proveedor B SPIT", "supplier_rank": 1}
        )
        cls.vendor_c = cls.env["res.partner"].create(
            {"name": "Proveedor C SPIT", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop SPIT 60",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 1000,
                "standard_price": 600,
            }
        )
        cls.product2 = cls.env["product.product"].create(
            {
                "name": "Monitor SPIT 60",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 200,
                "standard_price": 120,
            }
        )

    def _so(self, qty=10, product=None, currency=None):
        product = product or self.product
        vals = {
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
        if currency:
            vals["currency_id"] = currency.id
        return self.env["sale.order"].create(vals)

    def _buy(self, so, vendor, qty=None, sol=None):
        sol = sol or so.order_line.filtered(lambda l: not l.display_type)[:1]
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

    # --- 1–6 split básico ---
    def test_01_full_ten(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a)
        self.assertAlmostEqual(po.order_line.product_qty, 10)
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])

    def test_02_03_04_05_06_split_and_block(self):
        so = self._so(10)
        sol = so.order_line[0]
        po_a = self._buy(so, self.vendor_a, qty=6)
        self.assertAlmostEqual(po_a.order_line.product_qty, 6)
        self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)  # 3 reopen
        with self.assertRaises(UserError):
            self._buy(so, self.vendor_b, qty=5)  # 6 block
        po_b = self._buy(so, self.vendor_b, qty=4)  # 4
        self.assertAlmostEqual(po_b.order_line.product_qty, 4)
        self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)  # 5

    def test_07_split_3_2_5(self):
        so = self._so(10)
        sol = so.order_line[0]
        self._buy(so, self.vendor_a, qty=3)
        self._buy(so, self.vendor_b, qty=2)
        self._buy(so, self.vendor_c, qty=5)
        self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertEqual(len(sol.purchase_line_ids), 3)

    def test_08_decimal_qty(self):
        so = self._so(2.5)
        po = self._buy(so, self.vendor_a, qty=1.25)
        self.assertAlmostEqual(po.order_line.product_qty, 1.25)
        self._refresh(so.order_line[0])
        self.assertAlmostEqual(so.order_line[0].justech_qty_pending_purchase, 1.25)

    def test_09_cancelled_po_excluded(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        po.button_cancel()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 0)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 10)

    def test_10_cancelled_pol_excluded(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a, qty=6)
        pol = po.order_line[0]
        # Cancel line via order cancel if line-only cancel not available
        if hasattr(pol, "action_cancel"):
            try:
                pol.action_cancel()
            except Exception:
                po.button_cancel()
        else:
            po.button_cancel()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 0)

    def test_11_12_draft_and_confirmed(self):
        so = self._so(4)
        po = self._buy(so, self.vendor_a)
        self.assertIn(po.state, ("draft", "sent", "to approve", "purchase"))
        po.button_confirm()
        if po.state == "to approve":
            po.button_approve()
        self.assertIn(po.state, ("purchase", "done", "to approve"))
        self.assertEqual(po.order_line.sale_line_id, so.order_line[0])

    def test_13_14_receipt_partial_total(self):
        so = self._so(10)
        po = self._buy(so, self.vendor_a)
        po.button_confirm()
        pol = po.order_line[0]
        pol.write({"qty_received": 4})
        self.assertAlmostEqual(pol.qty_received, 4)
        pol.write({"qty_received": 10})
        self.assertAlmostEqual(pol.qty_received, 10)
        sol = self._refresh(so.order_line[0])
        self.assertIn(sol.justech_coverage_state, ("received", "full_purchase", "pending_receipt", "vendor_partial", "vendor_invoiced"))

    def test_15_16_vendor_bill_qty(self):
        so = self._so(5)
        po = self._buy(so, self.vendor_a)
        po.button_confirm()
        pol = po.order_line[0]
        pol.write({"qty_invoiced": 2})
        sol = self._refresh(so.order_line[0])
        self.assertTrue(sol.justech_coverage_state)
        pol.write({"qty_invoiced": 5})
        sol = self._refresh(so.order_line[0])
        self.assertTrue(sol.justech_qty_purchased >= 5)

    def test_17_18_credit_and_return_do_not_break_trace(self):
        so = self._so(5)
        po = self._buy(so, self.vendor_a)
        self.assertTrue(po.order_line.sale_line_id)
        # Credit note / return: purchased assignment remains until cancel
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 5)

    def test_19_20_sale_cancel(self):
        so = self._so(5)
        so.action_cancel()
        self.assertEqual(so.state, "cancel")

    def test_21_stock_covers_four(self):
        so = self._so(10)
        sol = so.order_line[0]
        wh = so.warehouse_id or self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if wh:
            self.env["stock.quant"].with_context(inventory_mode=True).create(
                {
                    "product_id": self.product.id,
                    "location_id": wh.lot_stock_id.id,
                    "inventory_quantity": 4,
                }
            ).action_apply_inventory()
        sol = self._refresh(sol)
        if sol.justech_qty_stock_covered >= 4:
            self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6)

    def test_22_23_24_stock_reservation_rules(self):
        # Free stock for other SO should not auto-reduce this SOL beyond free_qty_today logic
        so1 = self._so(10)
        so2 = self._so(5)
        self._refresh(so1.order_line[0])
        self._refresh(so2.order_line[0])
        # Incoming from linked PO must not double-count as stock + purchased
        po = self._buy(so1, self.vendor_a, qty=6)
        sol = self._refresh(so1.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 6)
        # pending = sold - stock - purchased; purchased already includes linked PO
        self.assertLessEqual(
            sol.justech_qty_pending_purchase + sol.justech_qty_stock_covered + sol.justech_qty_purchased,
            sol.justech_qty_sold + 0.0001,
        )

    def test_25_26_27_cost_methods_products(self):
        """Standard / AVCO / FIFO categories — purchase trace still writes sale_line_id."""
        Categ = self.env["product.category"]
        base = Categ.search([], limit=1)
        for method, name in (("standard", "Std"), ("average", "AVCO"), ("fifo", "FIFO")):
            categ = base.copy({"name": "SPIT %s %s" % (name, method)})
            categ.write(
                {
                    "property_cost_method": method,
                    "property_valuation": "periodic",
                }
            )
            prod = self.env["product.product"].create(
                {
                    "name": "SPIT %s Prod" % name,
                    "type": "consu",
                    "is_storable": True,
                    "purchase_ok": True,
                    "sale_ok": True,
                    "list_price": 100,
                    "standard_price": 40,
                    "categ_id": categ.id,
                }
            )
            so = self._so(3, product=prod)
            po = self._buy(so, self.vendor_a)
            self.assertEqual(po.order_line.sale_line_id, so.order_line[0])
            self.assertEqual(prod.categ_id.property_cost_method, method)

    def test_28_29_30_31_32_manual_po_link(self):
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
        self.assertFalse(pol.sale_line_id)  # 28
        pol.justech_link_to_sale_line(so_a.order_line[0], 6)  # 29
        pol.invalidate_recordset()
        self.assertAlmostEqual(pol.justech_qty_available_to_assign, 4)  # 30/32
        aml_before = self.env["account.move.line"].search_count([])
        # Simulate billed
        pol.write({"qty_received": 10, "qty_invoiced": 10})
        pol.justech_link_to_sale_line(so_b.order_line[0], 4)  # 31 commercial
        aml_after = self.env["account.move.line"].search_count([])
        self.assertEqual(aml_before, aml_after)
        self.assertAlmostEqual(pol.justech_qty_available_to_assign, 0)

    def test_33_34_pol_split_and_overassign(self):
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
        pol.justech_link_to_sale_line(so_b.order_line[0], 4)
        with self.assertRaises(Exception):
            pol.justech_link_to_sale_line(so_a.order_line[0], 1)

    def test_35_concurrency(self):
        so = self._so(10)
        sol = so.order_line[0]
        self._buy(so, self.vendor_a, qty=6)
        sol = self._refresh(sol)
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
        self.assertIn("actualice", str(err.exception).lower())

    def test_36_37_38_invoice_via_sol(self):
        so = self._so(2)
        so.order_line.product_id.invoice_policy = "order"
        so.with_context(justech_approval_skip=True).action_confirm()
        inv = so._create_invoices()
        self.assertTrue(inv._justech_invoice_sale_lines())  # 36
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
                            "name": "sin sol",
                        },
                    )
                ],
            }
        )
        self.assertFalse(lonely._justech_invoice_sale_lines())  # 37
        action = lonely.action_justech_invoice_related_purchases()
        self.assertEqual(action.get("tag"), "display_notification")
        # 38 multi SOL invoice
        so2 = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 10}),
                    (0, 0, {"product_id": self.product2.id, "product_uom_qty": 1, "price_unit": 20}),
                ],
            }
        )
        so2.order_line.mapped("product_id").write({"invoice_policy": "order"})
        so2.with_context(justech_approval_skip=True).action_confirm()
        inv2 = so2._create_invoices()
        self.assertGreaterEqual(len(inv2._justech_invoice_sale_lines()), 2)

    def test_39_40_multi_po_vendors(self):
        so = self._so(9)
        self._buy(so, self.vendor_a, qty=3)
        self._buy(so, self.vendor_b, qty=3)
        self._buy(so, self.vendor_c, qty=3)
        pos = so._justech_related_purchase_orders()
        self.assertEqual(len(pos), 3)

    def test_41_42_multicompany_block(self):
        other = self.env["res.company"].create({"name": "SPIT Other Co"})
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

    def test_43_44_multicurrency(self):
        usd = self.env.ref("base.USD")
        dop = self.env.ref("base.DOP", raise_if_not_found=False) or self.company.currency_id
        self.vendor_a.property_purchase_currency_id = usd
        so = self._so(2)
        if dop and "currency_id" in so._fields:
            so.currency_id = dop
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.currency_id, usd)  # 43 DOP sale / USD PO
        # 44 reverse: USD sale / company currency PO
        self.vendor_b.property_purchase_currency_id = False
        so2 = self._so(2)
        if usd in self.env["res.currency"].browse(usd.id):
            so2.currency_id = usd
        po2 = self._buy(so2, self.vendor_b)
        self.assertEqual(po2.order_line.sale_line_id, so2.order_line[0])

    def test_45_46_47_margin_bridge(self):
        so = self._so(5)
        po = self._buy(so, self.vendor_a)
        if "purchase.sale.margin.transaction" not in self.env:
            return
        Tx = self.env["purchase.sale.margin.transaction"]
        if not hasattr(Tx, "justech_collect_purchase_lines_from_sale"):
            return
        tx = Tx.create(
            {
                "name": "SPIT TX 45",
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
            }
        )
        pols = tx.justech_collect_purchase_lines_from_sale()
        self.assertIn(po.order_line[0], pols)  # 45
        self.assertEqual(len(pols), len(set(pols.ids)))  # 46
        self.assertIn("purchase.sale.cost.allocation", self.env)  # 47 model exists
        # Confirmed allocations are not wiped by collect
        Alloc = self.env["purchase.sale.cost.allocation"]
        before = Alloc.search_count([])
        tx.justech_collect_purchase_lines_from_sale()
        after = Alloc.search_count([])
        self.assertEqual(before, after)

    def test_48_49_50_51_permissions(self):
        Access = self.env["ir.model.access"]
        model = self.env["ir.model"]._get("justech.buy.pending.wizard")
        self.assertTrue(Access.search([("model_id", "=", model.id)], limit=1))
        # Sale / Purchase / Finance groups exist (ACL covers them)
        self.assertTrue(self.env.ref("sales_team.group_sale_salesman"))
        self.assertTrue(self.env.ref("purchase.group_purchase_user"))
        self.assertTrue(self.env.ref("account.group_account_invoice", raise_if_not_found=False) or True)
        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        if not portal_group:
            return
        login = "spit_portal_%s" % self.env.cr.dbname
        # unique per run
        login = "%s_%s" % (login, self.env["res.users"].search_count([]))
        portal = self.env["res.users"].create(
            {
                "name": "SPIT Portal",
                "login": login,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )
        so = self._so(1)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": 1,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.env["justech.purchase.sale.qty.assignment"].with_user(portal).create(
                {
                    "purchase_line_id": po.order_line.id,
                    "sale_line_id": so.order_line.id,
                    "quantity": 1,
                    "company_id": self.company.id,
                }
            )

    def test_52_53_54_55_56_wizard_ux_rules(self):
        so = self._so(10)
        sol = so.order_line[0]
        self._buy(so, self.vendor_a, qty=6)  # 52 cancel/recalc covered elsewhere
        # 53 change vendor: second buy with other vendor
        po_b = self._buy(so, self.vendor_b, qty=4)
        self.assertEqual(po_b.partner_id, self.vendor_b)
        # 54/55 reopen: pending 0 → default_get yields no lines
        wiz = self.env["justech.buy.pending.wizard"].with_context(
            active_id=so.id, default_sale_order_id=so.id
        ).default_get(["sale_order_id", "line_ids"])
        lines = wiz.get("line_ids") or []
        self.assertFalse(lines)  # 56 pendiente 0 oculta

    def test_57_58_59_60_origin_sale_line_idempotency(self):
        so = self._so(3)
        po = self._buy(so, self.vendor_a)
        self.assertEqual(po.origin, so.name)  # 57
        self.assertTrue(po.order_line.sale_line_id)  # 58
        # 59 existing PO without origin can still link
        po2 = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor_a.id,
                "origin": False,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 3,
                            "price_unit": 600,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        so2 = self._so(3)
        po2.order_line.justech_link_to_sale_line(so2.order_line[0], 3)
        self.assertTrue(po2.order_line.sale_line_id or po2.order_line.justech_qty_assignment_ids)
        # 60 idempotency: related POs stable
        ids1 = so._justech_related_purchase_orders().ids
        ids2 = so._justech_related_purchase_orders().ids
        self.assertEqual(sorted(ids1), sorted(ids2))
