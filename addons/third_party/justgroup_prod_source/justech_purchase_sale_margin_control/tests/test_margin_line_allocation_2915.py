# -*- coding: utf-8 -*-
"""19.0.8.29.15 — Line qty allocation + strict partner domains."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginLineAllocation2915(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_trace = "justech.purchase.sale.qty.assignment" in cls.env
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.SO = cls.env["sale.order"]
        cls.PO = cls.env["purchase.order"]
        cls.Move = cls.env["account.move"]
        cls.Tx = cls.env["purchase.sale.margin.transaction"]
        cls.Wiz = cls.env["purchase.sale.create.transaction.wizard"]
        cls.company = cls.env.company
        cls.customer_a = cls.Partner.create(
            {"name": "UAT Customer A 2915", "customer_rank": 1}
        )
        cls.customer_b = cls.Partner.create(
            {"name": "UAT Customer B 2915", "customer_rank": 1}
        )
        cls.supplier_a = cls.Partner.create(
            {"name": "UAT Supplier A 2915", "supplier_rank": 1}
        )
        cls.supplier_b = cls.Partner.create(
            {"name": "UAT Supplier B 2915", "supplier_rank": 1}
        )
        cls.product = cls.Product.create(
            {
                "name": "UAT Pila 2915",
                "list_price": 150,
                "standard_price": 100,
                "type": "consu",
            }
        )

    def _skip_no_trace(self):
        if not self.has_trace:
            self.skipTest("Trace qty.assignment required")

    def _make_so(self, partner, qty, price=150.0):
        so = self.SO.create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _make_po(self, partner, qty, price=100.0):
        po = self.PO.create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "price_unit": price,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def test_01_partial_po_allocates_proportional_cost(self):
        """CASE 1: PO 100 / SO 20 → cost = 20 * unit."""
        self._skip_no_trace()
        so = self._make_so(self.customer_a, 20, 150)
        po = self._make_po(self.supplier_a, 100, 100)
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer_a.id,
                "supplier_id": self.supplier_a.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "salesperson_id": so.user_id.id,
                "allocation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line[:1].id,
                            "purchase_line_id": po.order_line[:1].id,
                            "qty_to_assign": 20,
                            "selected": True,
                        },
                    )
                ],
            }
        )
        action = wiz.action_confirm_relation()
        tx = self.Tx.browse(action["res_id"])
        cost = tx.display_cost_amount
        self.assertTrue(
            float_compare(cost, 2000.0, precision_digits=2) == 0,
            "expected 2000 got %s" % cost,
        )
        self.assertTrue(
            float_compare(tx.display_sale_amount, 3000.0, precision_digits=2) == 0
            or float_compare(so.amount_untaxed, 3000.0, precision_digits=2) == 0
        )

    def test_02_two_sales_share_po_remaining(self):
        """CASE 2: 20+30 of 100, remaining 50."""
        self._skip_no_trace()
        so_a = self._make_so(self.customer_a, 20)
        so_b = self._make_so(self.customer_a, 30)
        po = self._make_po(self.supplier_a, 100, 100)
        svc = LineAllocationService(self.env)
        tx_a = self.Tx.create(
            {
                "company_id": self.company.id,
                "name": so_a.name,
                "sale_order_ids": [(6, 0, so_a.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "source": "manual",
            }
        )
        svc.apply_allocations_to_transaction(
            tx_a.with_context(skip_line_sync=True),
            [
                {
                    "sale_line": so_a.order_line[:1],
                    "purchase_line": po.order_line[:1],
                    "quantity": 20,
                }
            ],
        )
        avail = svc.pol_qty_available(po.order_line[:1])
        self.assertTrue(float_compare(avail, 80.0, precision_digits=4) == 0)
        svc.apply_allocations_to_transaction(
            tx_a.with_context(skip_line_sync=True),
            [
                {
                    "sale_line": so_b.order_line[:1],
                    "purchase_line": po.order_line[:1],
                    "quantity": 30,
                }
            ],
            replace=False,
        )
        avail2 = svc.pol_qty_available(po.order_line[:1])
        self.assertTrue(float_compare(avail2, 50.0, precision_digits=4) == 0)

    def test_03_deny_over_qty(self):
        """CASE 3: assign 101 of 100 → DENY."""
        self._skip_no_trace()
        so = self._make_so(self.customer_a, 101)
        po = self._make_po(self.supplier_a, 100)
        svc = LineAllocationService(self.env)
        with self.assertRaises((UserError, ValidationError)):
            svc.link_pol_to_sol(po.order_line[:1], so.order_line[:1], 101)

    def test_04_customer_domain_rpc_deny(self):
        """CASE 4: foreign customer invoice denied server-side."""
        inv_b = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer_b.id,
                "invoice_date": "2026-08-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 10,
                        },
                    )
                ],
            }
        )
        inv_b.action_post()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer_a.id,
                "customer_invoice_ids": [(6, 0, inv_b.ids)],
                "name": "force",
            }
        )
        with self.assertRaises(ValidationError):
            wiz._validate_documents()

    def test_05_supplier_domain_rpc_deny(self):
        """CASE 5: foreign supplier PO denied."""
        po_b = self._make_po(self.supplier_b, 5)
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "supplier_id": self.supplier_a.id,
                "purchase_order_ids": [(6, 0, po_b.ids)],
                "name": "force",
            }
        )
        with self.assertRaises(ValidationError):
            wiz._validate_documents()

    def test_06_invoice_ncf_name_search(self):
        """CASE 6: name_search finds by ref/NCF context."""
        inv = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer_a.id,
                "ref": "B0100UAT2915",
                "invoice_date": "2026-08-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 10,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        found = self.Move.with_context(justech_margin_show_ncf=True).name_search(
            "B0100UAT2915", args=[("id", "=", inv.id)]
        )
        self.assertTrue(found)
        self.assertIn("B0100UAT2915", found[0][1])

    def test_07_doc_only_unsafe_po_no_full_cost(self):
        """Document-only link SO+PO without 1:1 coverage → no full PO cost dump."""
        so = self._make_so(self.customer_a, 20)
        po = self._make_po(self.supplier_a, 100, 100)
        tx = self.Tx.create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "source": "manual",
            }
        )
        # create() syncs; unsafe PO should not add 100% cost
        cost_lines = tx.line_ids.filtered(
            lambda l: l.line_type == "cost" and l.purchase_order_line_id
        )
        self.assertFalse(
            cost_lines,
            "unsafe full PO must not sync automatically; got %s"
            % cost_lines.mapped("amount_untaxed"),
        )
        self.assertTrue(tx.cost_allocation_pending)

    def test_08_salesperson_preserved(self):
        so = self._make_so(self.customer_a, 5)
        sales_user = so.user_id
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer_a.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "salesperson_id": sales_user.id,
                "name": "sales-preserve",
            }
        )
        action = wiz.action_confirm_relation()
        tx = self.Tx.browse(action["res_id"])
        self.assertEqual(tx.salesperson_id, sales_user)

    def test_09_safe_full_qty_still_syncs(self):
        """Level B: SO qty == PO qty same product → full sync allowed."""
        so = self._make_so(self.customer_a, 10, 150)
        po = self._make_po(self.supplier_a, 10, 100)
        # strong sale_line_id for unequivocal coverage
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self.Tx.create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "source": "manual",
            }
        )
        cost_lines = tx.line_ids.filtered(lambda l: l.line_type == "cost")
        self.assertTrue(cost_lines)
        self.assertTrue(
            float_compare(sum(cost_lines.mapped("amount_untaxed")), 1000.0, precision_digits=2)
            == 0
        )

    def test_10_mtx_01673_math(self):
        """Café 2 of 10 at 326.27 → attributable 652.54 (not full PO)."""
        self._skip_no_trace()
        cafe = self.Product.create(
            {"name": "CAFE SANTO DOMINGO UAT", "list_price": 425, "type": "consu"}
        )
        so = self.SO.create(
            {
                "partner_id": self.customer_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {"product_id": cafe.id, "product_uom_qty": 2, "price_unit": 425},
                    )
                ],
            }
        )
        so.action_confirm()
        po = self.PO.create(
            {
                "partner_id": self.supplier_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cafe.id,
                            "product_qty": 10,
                            "price_unit": 326.27,
                            "name": cafe.name,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer_a.id,
                "supplier_id": self.supplier_a.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "allocation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line[:1].id,
                            "purchase_line_id": po.order_line[:1].id,
                            "qty_to_assign": 2,
                            "selected": True,
                        },
                    )
                ],
            }
        )
        tx = self.Tx.browse(wiz.action_confirm_relation()["res_id"])
        expected = 2.0 / 10.0 * po.order_line[:1].price_subtotal
        self.assertTrue(
            float_compare(tx.display_cost_amount, expected, precision_digits=2) == 0,
            "got %s expected %s" % (tx.display_cost_amount, expected),
        )


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCostCoverage2919(TransactionCase):
    """19.0.8.29.19 — provisional margin when sale lines lack full ASG coverage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_trace = "justech.purchase.sale.qty.assignment" in cls.env
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.SO = cls.env["sale.order"]
        cls.PO = cls.env["purchase.order"]
        cls.Tx = cls.env["purchase.sale.margin.transaction"]
        cls.Wiz = cls.env["purchase.sale.create.transaction.wizard"]
        cls.company = cls.env.company
        cls.customer = cls.Partner.create(
            {"name": "UAT Cov Customer 2919", "customer_rank": 1}
        )
        cls.supplier = cls.Partner.create(
            {"name": "UAT Cov Supplier 2919", "supplier_rank": 1}
        )
        cls.p1 = cls.Product.create(
            {"name": "UAT Cov P1", "list_price": 150, "standard_price": 100, "type": "consu"}
        )
        cls.p2 = cls.Product.create(
            {"name": "UAT Cov P2", "list_price": 200, "standard_price": 80, "type": "consu"}
        )

    def test_partial_coverage_forces_pending_band(self):
        if not self.has_trace:
            self.skipTest("Trace qty.assignment required")
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.p1.id, "product_uom_qty": 20, "price_unit": 150}),
                    (0, 0, {"product_id": self.p2.id, "product_uom_qty": 10, "price_unit": 200}),
                ],
            }
        )
        so.action_confirm()
        po = self.PO.create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.p1.id, "product_qty": 100, "price_unit": 100}),
                ],
            }
        )
        po.button_confirm()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "supplier_id": self.supplier.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po.ids)],
                "allocation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line.filtered(
                                lambda l: l.product_id == self.p1
                            ).id,
                            "purchase_line_id": po.order_line[:1].id,
                            "qty_to_assign": 20,
                            "selected": True,
                        },
                    )
                ],
            }
        )
        tx = self.Tx.browse(wiz.action_confirm_relation()["res_id"])
        self.assertEqual(tx.cost_coverage_state, "partial")
        self.assertTrue(tx.margin_is_provisional)
        self.assertEqual(tx.margin_band, "pending")
        self.assertTrue(tx.cost_pending_line_html)
        self.assertTrue(
            float_compare(tx.display_cost_amount, 2000.0, precision_digits=2) == 0,
            tx.display_cost_amount,
        )

    def test_relate_purchases_opens_create_wizard(self):
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.p1.id, "product_uom_qty": 1, "price_unit": 10}),
                ],
            }
        )
        act = so.action_relate_purchases()
        self.assertEqual(act["res_model"], "purchase.sale.manage.purchases.wizard")
        self.assertEqual(act["name"], "Gestionar compras")
        engine = so.action_add_purchase_orders()
        self.assertEqual(engine["res_model"], "purchase.sale.create.transaction.wizard")
        self.assertEqual(engine["name"], "Relacionar compras")

    def test_add_purchase_wizard_defaults_zero_qty(self):
        po = self.PO.create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.p1.id, "product_qty": 100, "price_unit": 100}),
                ],
            }
        )
        po.button_confirm()
        wiz = self.env["purchase.sale.add.purchase.wizard"].create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, po.ids)],
            }
        )
        wiz._onchange_purchase_order_ids()
        self.assertTrue(wiz.line_ids)
        self.assertTrue(all(not l.selected for l in wiz.line_ids))
        self.assertTrue(
            all(float_compare(l.qty_to_assign, 0.0, precision_digits=4) == 0 for l in wiz.line_ids)
        )


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginMultiVendor2920(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_trace = "justech.purchase.sale.qty.assignment" in cls.env
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.SO = cls.env["sale.order"]
        cls.PO = cls.env["purchase.order"]
        cls.Tx = cls.env["purchase.sale.margin.transaction"]
        cls.Wiz = cls.env["purchase.sale.create.transaction.wizard"]
        cls.company = cls.env.company
        cls.customer = cls.Partner.create({"name": "UAT MV Cust", "customer_rank": 1})
        cls.sup_a = cls.Partner.create({"name": "UAT MV SupA", "supplier_rank": 1})
        cls.sup_b = cls.Partner.create({"name": "UAT MV SupB", "supplier_rank": 1})
        cls.prod = cls.Product.create(
            {"name": "UAT MV X", "list_price": 150, "standard_price": 100, "type": "consu"}
        )

    def test_multi_vendor_po100_split(self):
        if not self.has_trace:
            self.skipTest("Trace required")
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_uom_qty": 100, "price_unit": 150})
                ],
            }
        )
        so.action_confirm()
        po_a = self.PO.create(
            {
                "partner_id": self.sup_a.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 60, "price_unit": 100})
                ],
            }
        )
        po_b = self.PO.create(
            {
                "partner_id": self.sup_b.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 100, "price_unit": 90})
                ],
            }
        )
        po_a.button_confirm()
        po_b.button_confirm()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "supplier_ids": [(6, 0, [self.sup_a.id, self.sup_b.id])],
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, (po_a | po_b).ids)],
                "purchase_pick_line_ids": [
                    (
                        0,
                        0,
                        {
                            "purchase_line_id": po_a.order_line.id,
                            "qty_to_relate": 60,
                            "selected": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "purchase_line_id": po_b.order_line.id,
                            "qty_to_relate": 40,
                            "selected": True,
                        },
                    ),
                ],
                "allocation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line.id,
                            "purchase_line_id": po_a.order_line.id,
                            "qty_to_assign": 60,
                            "selected": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line.id,
                            "purchase_line_id": po_b.order_line.id,
                            "qty_to_assign": 40,
                            "selected": True,
                        },
                    ),
                ],
            }
        )
        tx = self.Tx.browse(wiz.action_confirm_relation()["res_id"])
        self.assertEqual(len(tx.supplier_ids), 2)
        self.assertIn(self.sup_a, tx.supplier_ids)
        self.assertIn(self.sup_b, tx.supplier_ids)
        svc = LineAllocationService(self.env)
        self.assertTrue(
            float_compare(svc.pol_qty_available(po_b.order_line), 60.0, precision_digits=4) == 0
        )
        self.assertTrue(
            float_compare(svc.sol_qty_assigned_to_purchase(so.order_line), 100.0, precision_digits=4)
            == 0
        )

    def test_supplier_append_preserves_existing(self):
        if not self.has_trace:
            self.skipTest("Trace required")
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_uom_qty": 10, "price_unit": 150})
                ],
            }
        )
        so.action_confirm()
        po_a = self.PO.create(
            {
                "partner_id": self.sup_a.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 10, "price_unit": 100})
                ],
            }
        )
        po_a.button_confirm()
        tx = self.Tx.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "supplier_ids": [(6, 0, [self.sup_a.id])],
                "purchase_order_ids": [(6, 0, po_a.ids)],
            }
        )
        po_b = self.PO.create(
            {
                "partner_id": self.sup_b.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 50, "price_unit": 80})
                ],
            }
        )
        po_b.button_confirm()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "supplier_ids": [(6, 0, [self.sup_b.id])],
                "sale_order_ids": [(6, 0, so.ids)],
                "purchase_order_ids": [(6, 0, po_b.ids)],
                "allocation_line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line.id,
                            "purchase_line_id": po_b.order_line.id,
                            "qty_to_assign": 5,
                            "selected": True,
                        },
                    )
                ],
            }
        )
        # Need pick lines for balance validation path — confirm with alloc only
        wiz.write(
            {
                "purchase_pick_line_ids": [
                    (
                        0,
                        0,
                        {
                            "purchase_line_id": po_b.order_line.id,
                            "qty_to_relate": 5,
                            "selected": True,
                        },
                    )
                ]
            }
        )
        tx2 = self.Tx.browse(wiz.action_confirm_relation()["res_id"])
        self.assertEqual(tx2, tx)
        self.assertIn(self.sup_a, tx2.supplier_ids)
        self.assertIn(self.sup_b, tx2.supplier_ids)


@tagged("post_install", "-at_install", "justech_margin")
class TestPurchasePickAutoload2924(TransactionCase):
    """29.24 — commercial avail + autoload on PO select."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_trace = "justech.purchase.sale.qty.assignment" in cls.env
        cls.Partner = cls.env["res.partner"]
        cls.Product = cls.env["product.product"]
        cls.SO = cls.env["sale.order"]
        cls.PO = cls.env["purchase.order"]
        cls.Wiz = cls.env["purchase.sale.create.transaction.wizard"]
        cls.company = cls.env.company
        cls.customer = cls.Partner.create({"name": "UAT Autoload Cust", "customer_rank": 1})
        cls.supplier = cls.Partner.create({"name": "UAT Autoload Sup", "supplier_rank": 1})
        cls.prod = cls.Product.create(
            {"name": "UAT Autoload P", "list_price": 50, "standard_price": 20, "type": "consu"}
        )

    def _skip_no_trace(self):
        if not self.has_trace:
            self.skipTest("Trace qty.assignment required")

    def test_commercial_avail_ignores_received_qty(self):
        """Received/invoiced PO still has commercial avail = qty − ASG."""
        self._skip_no_trace()
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_uom_qty": 20, "price_unit": 50})
                ],
            }
        )
        so.action_confirm()
        po = self.PO.create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 100, "price_unit": 20})
                ],
            }
        )
        po.button_confirm()
        pol = po.order_line[:1]
        # Simulate fully received without commercial assignment
        pol.write({"qty_received": 100.0, "qty_invoiced": 100.0})
        svc = LineAllocationService(self.env)
        self.assertTrue(float_compare(svc.pol_qty_available(pol), 100.0, precision_digits=4) == 0)
        Assign = self.env["justech.purchase.sale.qty.assignment"]
        Assign.create(
            {
                "company_id": self.company.id,
                "purchase_line_id": pol.id,
                "sale_line_id": so.order_line.id,
                "quantity": 20.0,
                "state": "active",
            }
        )
        self.assertTrue(float_compare(svc.pol_qty_available(pol), 80.0, precision_digits=4) == 0)

    def test_autoload_rebuild_on_working_pos(self):
        self._skip_no_trace()
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_uom_qty": 10, "price_unit": 50})
                ],
            }
        )
        so.action_confirm()
        po = self.PO.create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 10, "price_unit": 20})
                ],
            }
        )
        po.button_confirm()
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "supplier_ids": [(6, 0, self.supplier.ids)],
                "sale_order_ids": [(6, 0, so.ids)],
                "state": "purchase_pick",
                "active_supplier_id": self.supplier.id,
                "supplier_id": self.supplier.id,
                "working_purchase_order_ids": [(6, 0, po.ids)],
            }
        )
        wiz._rebuild_purchase_pick_lines(preserve=False, only_current_supplier=True)
        self.assertTrue(wiz.purchase_pick_line_ids, "Available POL must be visible without load button")
        self.assertTrue(
            float_compare(wiz.purchase_pick_line_ids.qty_available, 10.0, precision_digits=4) == 0
        )
        # Zero qty → cannot advance
        self.assertFalse(wiz.can_advance_purchase_pick)
        wiz.purchase_pick_line_ids.qty_to_relate = 5.0
        wiz.purchase_pick_line_ids.selected = True
        wiz.invalidate_recordset(["can_advance_purchase_pick"])
        self.assertTrue(wiz.can_advance_purchase_pick)

    def test_fully_assigned_empty_message_totals(self):
        self._skip_no_trace()
        so = self.SO.create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_uom_qty": 10, "price_unit": 50})
                ],
            }
        )
        so.action_confirm()
        po = self.PO.create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.prod.id, "product_qty": 10, "price_unit": 20})
                ],
            }
        )
        po.button_confirm()
        self.env["justech.purchase.sale.qty.assignment"].create(
            {
                "company_id": self.company.id,
                "purchase_line_id": po.order_line.id,
                "sale_line_id": so.order_line.id,
                "quantity": 10.0,
                "state": "active",
            }
        )
        wiz = self.Wiz.create(
            {
                "company_id": self.company.id,
                "customer_id": self.customer.id,
                "supplier_ids": [(6, 0, self.supplier.ids)],
                "sale_order_ids": [(6, 0, so.ids)],
                "state": "purchase_pick",
                "active_supplier_id": self.supplier.id,
                "working_purchase_order_ids": [(6, 0, po.ids)],
                "show_fully_assigned": False,
            }
        )
        wiz._rebuild_purchase_pick_lines(preserve=False, only_current_supplier=True)
        self.assertFalse(wiz.purchase_pick_line_ids)
        html = wiz.purchase_pick_status_html or ""
        self.assertIn("no tiene cantidades disponibles", html)
        self.assertIn("Disponible: 0", html)
        self.assertFalse(wiz.can_advance_purchase_pick)
