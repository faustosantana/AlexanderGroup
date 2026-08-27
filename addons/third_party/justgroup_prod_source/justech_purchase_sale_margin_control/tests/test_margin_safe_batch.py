# -*- coding: utf-8 -*-
"""19.0.8.16.0 — SAFE batch consolidation: dry-run, REVIEW/CONFLICT skip, no dupes."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginSafeBatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "SAFE Batch Cliente", "customer_rank": 1}
        )
        cls.other_customer = cls.env["res.partner"].create(
            {"name": "SAFE Batch Otro", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "SAFE Batch Vendor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "SAFE Batch Product",
                "type": "consu",
                "list_price": 1750,
                "standard_price": 677.6,
            }
        )
        cls.Tx = cls.env["purchase.sale.margin.transaction"]

    def _so(self, partner=None, price=1750):
        so = self.env["sale.order"].create(
            {
                "partner_id": (partner or self.customer).id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": price})
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, price=677.6):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def _inv(self, so, price=1750):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "invoice_date": "2026-06-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _bill(self, po, price=677.6):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": po.partner_id.id,
                "invoice_date": "2026-06-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )

    def _fragment(self, so, with_cost=True, with_inv=True):
        po = bill = inv = self.env["purchase.order"]
        ctx = dict(allow_parallel_margin_tx=True)
        cost_tx = sale_tx = self.Tx.browse()
        if with_cost:
            po = self._po()
            bill = self._bill(po)
            cost_tx = self.Tx.with_context(**ctx).create(
                {
                    "company_id": self.company.id,
                    "customer_id": so.partner_id.id,
                    "sale_order_ids": [(6, 0, [so.id])],
                    "purchase_order_ids": [(6, 0, [po.id])],
                    "vendor_bill_ids": [(6, 0, [bill.id])],
                }
            )
        if with_inv:
            inv = self._inv(so)
            sale_tx = self.Tx.with_context(**ctx).create(
                {
                    "company_id": self.company.id,
                    "customer_id": so.partner_id.id,
                    "sale_order_ids": [(6, 0, [so.id])],
                    "customer_invoice_ids": [(6, 0, [inv.id])],
                }
            )
        return cost_tx | sale_tx, po, bill, inv

    def test_01_batch_safe_consolidation(self):
        so = self._so()
        txs, po, bill, inv = self._fragment(so)
        self.assertEqual(len(txs), 2)
        res = self.Tx.consolidate_if_safe(so)
        self.assertEqual(res["result"], "CONSOLIDATED")
        active = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertEqual(len(active), 1)
        self.assertIn(po, active.purchase_order_ids)
        self.assertIn(bill, active.vendor_bill_ids)
        self.assertIn(inv, active.customer_invoice_ids)

    def test_02_dry_run_does_not_write(self):
        so = self._so()
        txs, _po, _bill, _inv = self._fragment(so)
        preview = self.Tx.preview_safe_consolidation(so)
        self.assertEqual(preview["result"], "SAFE_OK")
        self.Tx.consolidate_sale_transactions(so, dry_run=True)
        still = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertEqual(len(still), 2)
        self.assertFalse(any(t.is_merged for t in txs))

    def test_03_review_not_touched(self):
        so = self._so()
        so2 = self._so()
        txs, po, _bill, _inv = self._fragment(so)
        # Share the cost MTX with another SO → REVIEW
        txs.filtered("purchase_order_ids").write({"sale_order_ids": [(4, so2.id)]})
        preview = self.Tx.preview_safe_consolidation(so)
        self.assertEqual(preview["result"], "REVIEW")
        merged = self.Tx.consolidate_sale_transactions(so)
        self.assertFalse(merged)
        active = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertGreaterEqual(len(active), 2)

    def test_04_conflict_not_touched(self):
        so = self._so()
        txs, _po, _bill, _inv = self._fragment(so)
        txs[0].customer_id = self.other_customer
        preview = self.Tx.preview_safe_consolidation(so)
        self.assertEqual(preview["result"], "CONFLICT")
        self.assertFalse(self.Tx.consolidate_sale_transactions(so))
        self.assertEqual(
            self.Tx.search_count([("sale_order_ids", "in", so.id), ("is_merged", "=", False)]),
            2,
        )

    def test_05_idempotence_preview(self):
        so = self._so()
        self._fragment(so)
        a = self.Tx.preview_safe_consolidation(so)
        b = self.Tx.preview_safe_consolidation(so)
        self.assertEqual(a["result"], b["result"])
        self.assertEqual(a["canonical_id"], b["canonical_id"])

    def test_06_double_consolidate_noop(self):
        so = self._so()
        self._fragment(so)
        r1 = self.Tx.consolidate_if_safe(so)
        canon = r1["canonical_id"]
        r2 = self.Tx.consolidate_if_safe(so)
        self.assertEqual(r2["result"], "ALREADY_CONSOLIDATED")
        self.assertEqual(r2["canonical_id"], canon)
        self.assertEqual(
            self.Tx.search_count([("sale_order_ids", "in", so.id), ("is_merged", "=", False)]),
            1,
        )

    def test_07_no_duplicate_bills(self):
        so = self._so()
        txs, _po, bill, _inv = self._fragment(so)
        txs[1].with_context(skip_vendor_bill_unique=True).write(
            {"vendor_bill_ids": [(4, bill.id)]}
        )
        self.Tx.consolidate_if_safe(so)
        active = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertEqual(len(active.vendor_bill_ids), 1)

    def test_08_no_duplicate_pos(self):
        so = self._so()
        txs, po, _bill, _inv = self._fragment(so)
        txs[1].write({"purchase_order_ids": [(4, po.id)]})
        self.Tx.consolidate_if_safe(so)
        active = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertEqual(len(active.purchase_order_ids), 1)

    def test_09_no_duplicate_invoice(self):
        so = self._so()
        txs, _po, _bill, inv = self._fragment(so)
        txs[0].write({"customer_invoice_ids": [(4, inv.id)]})
        self.Tx.consolidate_if_safe(so)
        active = self.Tx.search([("sale_order_ids", "in", so.id), ("is_merged", "=", False)])
        self.assertEqual(len(active.customer_invoice_ids), 1)

    def test_10_margin_unchanged(self):
        so = self._so()
        txs, _po, _bill, _inv = self._fragment(so)
        preview = self.Tx.preview_safe_consolidation(so)
        res = self.Tx.consolidate_if_safe(so)
        self.assertEqual(res["result"], "CONSOLIDATED")
        self.assertAlmostEqual(res["sale_after"], preview["sale_after"], places=2)
        self.assertAlmostEqual(res["cost_after"], preview["cost_after"], places=2)
        self.assertAlmostEqual(res["margin_after"], preview["margin_after"], places=2)

    def test_11_merged_into_correct(self):
        so = self._so()
        txs, _po, _bill, _inv = self._fragment(so)
        res = self.Tx.consolidate_if_safe(so)
        secondary = txs.filtered("is_merged")
        self.assertTrue(secondary)
        self.assertEqual(secondary.merged_into_id.id, res["canonical_id"])

    def test_12_secondary_not_operational(self):
        so = self._so()
        self._fragment(so)
        self.Tx.consolidate_if_safe(so)
        so.invalidate_recordset()
        self.assertEqual(so.margin_transaction_count, 1)
        self.assertFalse(so.margin_transaction_ids.filtered("is_merged"))

    def test_13_accounting_cost_uses_move_signed_amount(self):
        """Posted vendor bill company amount is amount_untaxed_signed, not header FX."""
        bill = self.env["account.move"].search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("currency_id", "!=", self.company.currency_id.id),
                ("amount_untaxed_signed", "!=", 0),
            ],
            limit=1,
        )
        if not bill:
            self.skipTest("no posted foreign-currency vendor bill in this DB")
        tx = self.Tx.search(
            [("vendor_bill_ids", "in", bill.id), ("is_merged", "=", False)],
            limit=1,
        )
        if not tx:
            self.skipTest("foreign-currency bill is not on an active MTX")
        line = tx.line_ids.filtered(
            lambda l: l.account_move_id == bill and l.line_type == "cost" and l.data_origin == "accounting"
        )
        if not line:
            tx._sync_lines_from_documents()
            line = tx.line_ids.filtered(
                lambda l: l.account_move_id == bill and l.line_type == "cost" and l.data_origin == "accounting"
            )
        self.assertTrue(line, "missing accounting cost line for %s" % bill.name)
        for rec in line:
            self.assertAlmostEqual(
                rec.amount_company_currency, abs(bill.amount_untaxed_signed), places=2
            )
