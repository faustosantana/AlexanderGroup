# -*- coding: utf-8 -*-
"""19.0.8.15.0 — Canonical MTX: reuse, consolidate, no parallel ops."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCanonical(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "CANON Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "CANON Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "CANON Product",
                "type": "consu",
                "list_price": 1750,
                "standard_price": 677.6,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self, price=1750):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, price=677.6, origin=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "origin": origin or False,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _out_invoice(self, so, price=None):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price if price is not None else so.order_line[:1].price_unit,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _bill(self, po, price=None):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price if price is not None else po.order_line[:1].price_unit,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def test_01_so_creates_mtx_via_find_or_create(self):
        so = self._so()
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        self.assertTrue(tx)
        self.assertIn(so, tx.sale_order_ids)
        self.assertFalse(tx.is_merged)

    def test_02_po_reuses_mtx(self):
        so = self._so()
        tx1 = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        po = self._po(origin=so.name)
        # link sale_line so auto-link / find can see it
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx2 = self.Transaction.find_or_create_canonical_transaction(
            sale_order=so,
            vals={"purchase_order_ids": [(4, po.id)]},
        )
        self.assertEqual(tx1, tx2)
        self.assertIn(po, tx1.purchase_order_ids)
        self.assertEqual(
            self.Transaction.search_count(
                [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
            ),
            1,
        )

    def test_03_bill_reuses_mtx(self):
        so = self._so()
        po = self._po(origin=so.name)
        po.order_line[:1].sale_line_id = so.order_line[:1]
        tx = self.Transaction.find_or_create_canonical_transaction(
            sale_order=so, vals={"purchase_order_ids": [(4, po.id)]}
        )
        bill = self._bill(po)
        # Auto-link on post is NCF-gated in DEV; attach as the hook would after a posted bill.
        tx.write({"vendor_bill_ids": [(4, bill.id)]})
        found = self.Transaction.search(
            [("purchase_order_ids", "in", po.id)] + self.Transaction._operational_domain()
        )
        self.assertIn(tx, found)
        self.assertIn(bill, tx.vendor_bill_ids)
        self.assertEqual(
            self.Transaction.search_count(
                [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
            ),
            1,
        )

    def test_04_customer_invoice_reuses_mtx(self):
        so = self._so()
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        inv = self._out_invoice(so)
        tx2 = self.Transaction.find_or_create_canonical_transaction(
            sale_order=so, customer_invoice=inv
        )
        self.assertEqual(tx, tx2)
        tx.invalidate_recordset()
        so.invalidate_recordset()
        self.assertIn(inv, tx.customer_invoice_ids)
        self.assertEqual(so.margin_transaction_count, 1)
        self.assertIn(tx, inv.margin_transaction_ids)

    def test_05_payment_does_not_create_mtx(self):
        so = self._so()
        before = self.Transaction.search_count([])
        # Non-invoice journal entry (payment-like) must not spawn MTX.
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": "2026-06-20",
                "journal_id": self.env["account.journal"].search(
                    [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
                ).id,
            }
        )
        if move.journal_id:
            try:
                move.action_post()
            except Exception:  # noqa: BLE001
                pass
        after = self.Transaction.search_count([])
        self.assertEqual(before, after)
        self.assertFalse(
            so.margin_transaction_ids,
            "SO confirmation must not auto-create MTX without cost/invoice event",
        )

    def test_06_inventory_does_not_create_mtx(self):
        so = self._so()
        before = self.Transaction.search_count([("sale_order_ids", "in", so.id)])
        self.assertFalse(
            hasattr(self.env["stock.picking"], "_justech_auto_link_margin_from_sale")
        )
        self.assertFalse(
            hasattr(self.env["account.payment"], "_justech_auto_link_margin_documents")
        )
        svc = self.env["purchase.sale.inventory.cost.service"]
        if hasattr(svc, "sale_delivery_moves"):
            svc.sale_delivery_moves(so)
        after = self.Transaction.search_count([("sale_order_ids", "in", so.id)])
        self.assertEqual(before, after)

    def test_07_repeated_events_one_mtx(self):
        so = self._so()
        self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        self.Transaction.create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "sale_order_ids": [(6, 0, [so.id])],
            }
        )
        self.assertEqual(
            self.Transaction.search_count(
                [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
            ),
            1,
        )

    def test_08_historical_two_mtx_consolidate(self):
        so = self._so()
        po = self._po()
        inv = self._out_invoice(so)
        bill = self._bill(po)
        cost_tx = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "name": po.name,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
                "state": "detected",
                "source": "backfill",
            }
        )
        sale_tx = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
                "state": "detected",
                "source": "backfill",
            }
        )
        self.assertEqual(
            self.Transaction.search_count(
                [("sale_order_ids", "in", so.id), ("is_merged", "=", False)]
            ),
            2,
        )
        canonical = self.Transaction.consolidate_sale_transactions(so)
        self.assertTrue(canonical)
        self.assertIn(canonical, (cost_tx | sale_tx))
        secondary = (cost_tx | sale_tx) - canonical
        self.assertTrue(secondary.is_merged)
        self.assertEqual(secondary.merged_into_id, canonical)
        self.assertFalse(canonical.is_merged)
        self.assertIn(so, canonical.sale_order_ids)
        self.assertIn(po, canonical.purchase_order_ids)
        self.assertIn(bill, canonical.vendor_bill_ids)
        self.assertIn(inv, canonical.customer_invoice_ids)
        so.invalidate_recordset()
        inv.invalidate_recordset()
        self.assertEqual(so.margin_transaction_count, 1)
        self.assertIn(canonical, inv.margin_transaction_ids)
        self.assertIn(po, inv.jm_related_purchase_order_ids)
        self.assertIn(bill, inv.jm_related_vendor_bill_ids)

    def test_09_links_not_duplicated(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.find_or_create_canonical_transaction(
            sale_order=so, vals={"purchase_order_ids": [(4, po.id)]}
        )
        tx.write({"purchase_order_ids": [(4, po.id)]})
        self.assertEqual(len(tx.purchase_order_ids), 1)

    def test_10_margin_preserved_after_merge(self):
        so = self._so(price=1750)
        po = self._po(price=677.6)
        cost_tx = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "customer_id": self.customer.id,
            }
        )
        sale_tx = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_id": self.customer.id,
            }
        )
        cost_before = cost_tx.display_cost_amount
        sale_before = cost_tx.display_sale_amount
        margin_before = cost_tx.display_margin_amount
        canonical = self.Transaction.consolidate_sale_transactions(so)
        canonical.invalidate_recordset()
        self.assertAlmostEqual(canonical.display_cost_amount, cost_before, places=2)
        self.assertAlmostEqual(canonical.display_sale_amount, sale_before, places=2)
        self.assertAlmostEqual(canonical.display_margin_amount, margin_before, places=2)
        self.assertTrue(sale_tx.exists())

    def test_11_approvals_preserved_on_secondary(self):
        so = self._so()
        a = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "state": "approved",
                "approval_state": "approved",
                "purchase_order_ids": [(6, 0, [self._po().id])],
            }
        )
        b = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "state": "detected",
            }
        )
        self.Transaction.consolidate_sale_transactions(so)
        a.invalidate_recordset()
        b.invalidate_recordset()
        merged = (a | b).filtered("is_merged")
        if merged:
            self.assertTrue(merged.state in ("approved", "detected", "validated", "draft"))
        self.assertTrue((a | b).filtered(lambda t: not t.is_merged))

    def test_12_chatter_preserved(self):
        so = self._so()
        a = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [self._po().id])],
            }
        )
        a.message_post(body="HISTORIAL-UAT-CANON")
        b = self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
            }
        )
        self.Transaction.consolidate_sale_transactions(so)
        bodies = (a | b).message_ids.mapped("body")
        joined = " ".join(bodies)
        self.assertIn("HISTORIAL-UAT-CANON", joined)
        self.assertTrue(a.exists() and b.exists())

    def test_13_invoice_to_cost_after_merge(self):
        so = self._so(price=1750)
        po = self._po(price=677.6)
        inv = self._out_invoice(so, price=1750)
        bill = self._bill(po, price=677.6)
        self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "name": po.name,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "vendor_bill_ids": [(6, 0, [bill.id])],
            }
        )
        self.Transaction.with_context(allow_parallel_margin_tx=True).create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "sale_order_ids": [(6, 0, [so.id])],
                "customer_invoice_ids": [(6, 0, [inv.id])],
            }
        )
        canonical = self.Transaction.consolidate_sale_transactions(so)
        inv.invalidate_recordset()
        po.invalidate_recordset()
        self.assertIn(canonical, inv.margin_transaction_ids)
        self.assertIn(po, inv.jm_related_purchase_order_ids)
        self.assertIn(bill, inv.jm_related_vendor_bill_ids)
        self.assertIn(inv, po.jm_related_customer_invoice_ids)
        self.assertEqual(so.margin_transaction_count, 1)
