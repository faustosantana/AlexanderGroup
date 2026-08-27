# -*- coding: utf-8 -*-
"""Coverage: inventory + open PO = complete (not pending receive)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
    CostManagementService,
)
from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)


@tagged("post_install", "-at_install", "justech_margin")
class TestHubCoverageInventoryPlusPo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env["res.partner"].create({"name": "UAT Cover Cust"})
        self.supplier = self.env["res.partner"].create(
            {"name": "UAT Cover Vendor", "supplier_rank": 1}
        )
        self.product = self.env["product.product"].create(
            {
                "name": "UAT Cover Product",
                "type": "consu",
                "list_price": 100.0,
                "standard_price": 60.0,
            }
        )
        self.so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 300.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        self.sol = self.so.order_line[0]
        self.tx = self.env["purchase.sale.margin.transaction"].create(
            {
                "name": "UAT-COVER",
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [self.so.id])],
                "customer_id": self.partner.id,
            }
        )

    def _add_inventory(self, qty, unit=65.0):
        return self.env["purchase.sale.margin.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "line_type": "cost",
                "cost_source": "inventory",
                "data_origin": "manual",
                "state": "confirmed",
                "quantity": qty,
                "amount_untaxed": qty * unit,
                "product_id": self.product.id,
                "sale_order_line_id": self.sol.id,
                "sale_order_id": self.so.id,
                "description": "Inventario UAT",
            }
        )

    def _add_po(self, qty, price=65.0):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "price_unit": price,
                            "sale_line_id": self.sol.id,
                        },
                    )
                ],
            }
        )
        return po, po.order_line[0]

    def test_case1_inventory_150_po_150_complete(self):
        self._add_inventory(150.0)
        self._add_po(150.0)
        rows, _ = CostManagementService(self.env).build_demand_rows(
            self.so, transaction=self.tx
        )
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["sold_qty"], 300.0)
        self.assertEqual(r["historical_qty"], 150.0)
        self.assertEqual(r["purchase_qty"], 150.0)
        self.assertEqual(r["pending_qty"], 0.0)
        self.assertEqual(r["line_status"], "complete")

    def test_case2_inventory_150_po_100_partial(self):
        self._add_inventory(150.0)
        self._add_po(100.0)
        rows, _ = CostManagementService(self.env).build_demand_rows(
            self.so, transaction=self.tx
        )
        r = rows[0]
        self.assertEqual(r["pending_qty"], 50.0)
        self.assertEqual(r["line_status"], "partial")

    def test_refresh_does_not_exclude_inventory(self):
        inv = self._add_inventory(150.0)
        po, pol = self._add_po(150.0)
        self.tx.write({"purchase_order_ids": [(4, po.id)]})
        LineAllocationService(self.env).refresh_estimated_costs_from_live_assignments(
            self.tx
        )
        inv.invalidate_recordset()
        self.assertEqual(inv.state, "confirmed")
        rows, _ = CostManagementService(self.env).build_demand_rows(
            self.so, transaction=self.tx
        )
        self.assertEqual(rows[0]["pending_qty"], 0.0)
        self.assertEqual(rows[0]["line_status"], "complete")

    def test_refresh_reinstates_wrongly_excluded_inventory(self):
        inv = self._add_inventory(150.0)
        inv.write({"state": "excluded"})
        self._add_po(150.0)
        LineAllocationService(self.env).refresh_estimated_costs_from_live_assignments(
            self.tx
        )
        inv.invalidate_recordset()
        self.assertEqual(inv.state, "confirmed")
        self.assertTrue(
            float_compare(
                CostManagementService(self.env)
                .build_demand_rows(self.so, transaction=self.tx)[0][0]["pending_qty"],
                0.0,
                precision_digits=4,
            )
            == 0
        )
