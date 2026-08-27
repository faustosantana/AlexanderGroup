# -*- coding: utf-8 -*-
"""19.0.8.29.37 — Idempotent estimated cost refresh (no 3+3→6)."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)


@tagged("post_install", "-at_install", "justech_margin_integrity_2937")
class TestMarginIntegrity2937(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "UAT Integrity Customer", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "UAT Integrity Vendor", "supplier_rank": 1}
        )
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "UAT INT A",
                "type": "consu",
                "list_price": 500,
                "standard_price": 300,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "UAT INT B",
                "type": "consu",
                "list_price": 500,
                "standard_price": 300,
            }
        )

    def _make_so_po_linked(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_uom_qty": 3,
                            "price_unit": 500,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_b.id,
                            "product_uom_qty": 3,
                            "price_unit": 500,
                        },
                    ),
                ],
            }
        )
        so.action_confirm()
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_qty": 3,
                            "price_unit": 300,
                            "sale_line_id": so.order_line[0].id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_b.id,
                            "product_qty": 3,
                            "price_unit": 300,
                            "sale_line_id": so.order_line[1].id,
                        },
                    ),
                ],
            }
        )
        Tx = self.env["purchase.sale.margin.transaction"]
        tx = Tx.find_or_create_canonical_transaction(
            sale_order=so,
            vals={
                "company_id": self.company.id,
                "customer_id": self.partner.id,
            },
        )
        tx.write({"purchase_order_ids": [(4, po.id)]})
        svc = LineAllocationService(self.env)
        # Historical buggy path: ADD twice with replace=False (3+3→6 without fix).
        for pol in po.order_line:
            amt = pol.price_subtotal
            svc.upsert_mtx_estimated_cost_line(tx, pol, 3.0, amt, replace=False)
            svc.upsert_mtx_estimated_cost_line(tx, pol, 3.0, amt, replace=False)
        # Canonical rewrite must collapse to live assigned qty.
        svc.refresh_estimated_costs_from_live_assignments(tx)
        return so, po, tx, svc

    def test_01_estimated_cost_1800_not_3600(self):
        so, po, tx, svc = self._make_so_po_linked()
        tx.invalidate_recordset()
        self.assertEqual(
            float_compare(tx.cost_estimated_amount, 1800.0, precision_digits=2),
            0,
            "cost=%s" % tx.cost_estimated_amount,
        )
        for line in tx.line_ids.filtered(
            lambda l: l.line_type == "cost" and l.state != "excluded"
        ):
            self.assertEqual(
                float_compare(line.quantity, 3.0, precision_digits=4),
                0,
                "qty=%s pol=%s" % (line.quantity, line.purchase_order_line_id.id),
            )

    def test_02_recompute_10x_idempotent(self):
        so, po, tx, svc = self._make_so_po_linked()
        costs = []
        qtys = []
        counts = []
        for _ in range(10):
            svc.refresh_estimated_costs_from_live_assignments(tx)
            tx.invalidate_recordset()
            active = tx.line_ids.filtered(
                lambda l: l.line_type == "cost" and l.state != "excluded"
            )
            costs.append(tx.cost_estimated_amount)
            qtys.append(sum(active.mapped("quantity")))
            counts.append(len(active))
        self.assertTrue(
            all(float_compare(c, 1800.0, precision_digits=2) == 0 for c in costs), costs
        )
        self.assertTrue(
            all(float_compare(q, 6.0, precision_digits=4) == 0 for q in qtys), qtys
        )
        self.assertTrue(all(n == counts[0] for n in counts), counts)

    def test_03_zero_purchase_price_blocked(self):
        Wiz = self.env["purchase.sale.cost.create.purchase.wizard"]
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_uom_qty": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        hub = self.env["purchase.sale.manage.purchases.wizard"].create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, so.ids)],
                "customer_id": self.partner.id,
            }
        )
        wiz = Wiz.create(
            {
                "hub_wizard_id": hub.id,
                "company_id": self.company.id,
                "supplier_id": self.vendor.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": so.order_line[0].id,
                            "product_id": self.product_a.id,
                            "product_name": self.product_a.display_name,
                            "pending_qty": 1,
                            "buy_qty": 1,
                            "sale_cover_qty": 1,
                            "price_unit": 0.0,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            wiz.action_goto_review()

    def test_04_cancelled_po_excluded_from_gate(self):
        so, po, tx, svc = self._make_so_po_linked()
        po.button_cancel()
        tx.invalidate_recordset()
        # Must not raise: cancelled PO with released coverage.
        tx._check_no_cancelled_documents()
        active = tx.line_ids.filtered(
            lambda l: l.line_type == "cost" and l.state != "excluded"
        )
        self.assertFalse(active)
        self.assertEqual(
            float_compare(tx.cost_estimated_amount or 0.0, 0.0, precision_digits=2),
            0,
        )

    def test_05_duplicate_sol_blocked_server_side(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_uom_qty": 3,
                            "price_unit": 500,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_qty": 3,
                            "price_unit": 300,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_qty": 3,
                            "price_unit": 300,
                        },
                    ),
                ],
            }
        )
        svc = LineAllocationService(self.env)
        svc.link_pol_to_sol(po.order_line[0], so.order_line[0], 3.0)
        with self.assertRaises(UserError):
            svc.link_pol_to_sol(po.order_line[1], so.order_line[0], 1.0)

    def test_06_unlink_clears_active_link_ux(self):
        so, po, tx, svc = self._make_so_po_linked()
        self.assertTrue(po.margin_link_sale_id)
        po.action_unlink_from_sale()
        po.invalidate_recordset()
        self.assertFalse(po.margin_link_sale_id)
        self.assertFalse(any(po.order_line.mapped("sale_line_id")))
