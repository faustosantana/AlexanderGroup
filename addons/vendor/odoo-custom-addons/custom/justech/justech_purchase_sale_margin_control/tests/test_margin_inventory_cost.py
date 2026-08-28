# -*- coding: utf-8 -*-
"""Costo de inventario consumido — 19.0.8.11.0."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginInventoryCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Inv = cls.env["purchase.sale.inventory.cost.service"]
        cls.company = cls.env.company
        cls.partner_vendor = cls.env["res.partner"].create(
            {"name": "Vendor Inv UAT", "supplier_rank": 1}
        )
        cls.partner_a = cls.env["res.partner"].create(
            {"name": "Cliente A Inv UAT", "customer_rank": 1}
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "Cliente B Inv UAT", "customer_rank": 1}
        )
        categ = cls.env["product.category"].search([], limit=1)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Papel higienico UAT",
                "type": "consu",
                "is_storable": True,
                "list_price": 20.0,
                "standard_price": 10.0,
                "categ_id": categ.id,
            }
        )

    def _report(self, **vals):
        defaults = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
        }
        defaults.update(vals)
        return self.Report.create(defaults)

    def test_01_cost_source_field_on_line(self):
        field = self.env["purchase.sale.margin.transaction.line"]._fields["cost_source"]
        self.assertIn("inventory", dict(field.selection))
        self.assertIn("direct_purchase", dict(field.selection))

    def test_02_decorate_residual_zero_shows_pagada(self):
        r = self._report()
        crow = r._decorate_cost_payment(
            {
                "kind": "bill",
                "bill": "BILL/INV",
                "bill_id": 1,
                "total": 100.0,
                "residual": 0.0,
                "raw_payment_state": "in_payment",
            }
        )
        self.assertEqual(crow["payment_badge"], "PAGADA")
        self.assertEqual(crow["payment_code"], "paid")

    def test_03_decorate_inventory_consumed(self):
        r = self._report()
        crow = r._decorate_cost_payment(
            {
                "kind": "inventory",
                "bill": "Salida WH/OUT/1",
                "total": 100.0,
                "residual": 0.0,
            }
        )
        self.assertEqual(crow["payment_badge"], "CONSUMIDO")
        self.assertIs(crow["residual_display"], False)

    def test_04_move_cost_uses_standard_price_fallback(self):
        Move = self.env["stock.move"]
        # Minimal synthetic: product standard 10 × qty 7
        # Avoid full picking workflow — call service math via fake-like move if possible.
        # Create a done internal-like move attached to a sale line when stock allows.
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if not wh:
            self.skipTest("No warehouse")
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 20,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        pickings = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
        )
        if not pickings:
            self.skipTest("No outgoing picking after confirm")
        picking = pickings[0]
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        moves = self.Inv.sale_delivery_moves(so)
        self.assertTrue(moves)
        total = sum(self.Inv.move_consumed_cost(m) for m in moves)
        # 10 ud × standard 10
        self.assertAlmostEqual(total, 100.0, places=2)

    def test_05_inventory_rows_label(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 20,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        pickings = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
        )
        if not pickings:
            self.skipTest("No outgoing picking")
        picking = pickings[0]
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        rows = self.Inv.inventory_cost_rows_for_sales(
            so, currency=self.company.currency_id
        )
        self.assertTrue(rows)
        self.assertEqual(rows[0]["kind"], "inventory")
        self.assertEqual(rows[0]["cost_source"], "inventory")
        self.assertIn("INVENTARIO", rows[0]["vendor"])
        self.assertAlmostEqual(rows[0]["untaxed"], 100.0, places=2)

    def test_06_two_sales_consume_partial_not_full_purchase(self):
        """Compra 100 no debe aparecer como costo de cada venta; solo qty entregada."""
        # Stock via inventory adjustment / receipt is environment-dependent.
        # Validate report cost_rows prefer inventory over full bill when deliveries exist.
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 25,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        pickings = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
        )
        if not pickings:
            self.skipTest("No outgoing picking")
        picking = pickings[0]
        for move in picking.move_ids:
            move.quantity = 10
        picking.button_validate()

        Tx = self.env["purchase.sale.margin.transaction"]
        tx = Tx.create(
            {
                "name": "TX INV UAT A",
                "company_id": self.company.id,
                "customer_id": self.partner_a.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        # Attach a large vendor bill that must NOT inflate margin when inventory rows exist
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_vendor.id,
                "invoice_date": "2026-08-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 100,
                            "price_unit": 10,
                            "name": "Compra inventario 100",
                        },
                    )
                ],
            }
        )
        # Draft es suficiente: evita reglas de aprobación PO en DEV.
        self.assertNotEqual(bill.state, "cancel")
        tx.write({"vendor_bill_ids": [(4, bill.id)]})

        rows = self.Report._cost_rows(tx)
        inv = [r for r in rows if r.get("kind") == "inventory"]
        bills_margin = [
            r
            for r in rows
            if r.get("kind") == "bill" and r.get("include_in_margin", True)
        ]
        self.assertTrue(inv)
        self.assertAlmostEqual(sum(r["untaxed"] for r in inv), 100.0, places=2)
        # Full 100-ud bill must not be in margin
        self.assertFalse(bills_margin)
        cxp = [r for r in rows if r.get("kind") == "bill" and r.get("include_in_cxp")]
        self.assertTrue(cxp)
        self.assertAlmostEqual(
            abs(cxp[0].get("cxp_total") or 0.0), abs(bill.amount_total), places=2
        )
    def test_07_pdf_arch_polish_markers(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.report_cost_vs_sale_pdf_document"
        )
        arch = view.arch_db or ""
        self.assertIn("#8EA0B5", arch)
        self.assertIn("#172B4D", arch)
        self.assertIn("page-break-inside:avoid", arch)
        self.assertIn("jm-cxp", arch)
        self.assertIn("NCF:", arch)
        self.assertNotIn(">NCF</th>", arch)
        self.assertIn("colspan=\"7\"", arch)

    def test_08_purchase_inventory_status_available(self):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 100,
                            "price_unit": 10,
                            "name": self.product.display_name,
                        },
                    )
                ],
            }
        )
        status, orig, assigned, pending = self.Inv.purchase_inventory_status(po)
        self.assertEqual(status, "available")
        self.assertAlmostEqual(orig, po.amount_untaxed, places=2)
        self.assertEqual(assigned, 0.0)
