# -*- coding: utf-8 -*-
"""19.0.8.29.9 — Origin-exact SO↔PO confirmation + backfill (no fake sale_line_id)."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginOriginRelation8299(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "Origin Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Origin Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Origin Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 400,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self, n_lines=1):
        lines = [
            (
                0,
                0,
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "price_unit": 1000,
                },
            )
            for _ in range(n_lines)
        ]
        so = self.env["sale.order"].create(
            {"partner_id": self.customer.id, "order_line": lines}
        )
        so.action_confirm()
        return so

    def _po(self, origin=None, confirm=True):
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
                            "price_unit": 400,
                        },
                    )
                ],
            }
        )
        if confirm:
            po.button_confirm()
        return po

    def test_01_origin_exact_confirms_without_sale_line_id(self):
        so = self._so()
        po = self._po(origin=so.name)
        self.assertFalse(po.order_line[:1].sale_line_id)
        klass, resolved = self.Transaction._classify_po_origin(po)
        self.assertEqual(klass, "ORIGIN_EXACT_SINGLE")
        self.assertEqual(resolved, so)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "customer_id": so.partner_id.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "detected",
                "source": "backfill",
                "is_uat_fixture": True,
            }
        )
        self.assertTrue(tx._has_origin_exact_trace())
        self.assertTrue(tx._has_confirmed_sale_po_relation())
        self.assertFalse(tx._has_strong_sale_po_trace())
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")
        cov, total, linked = tx._line_coverage_status()
        self.assertEqual(cov, "NONE")
        self.assertEqual(linked, 0)

    def test_02_origin_multiple_not_confirmed(self):
        so = self._so()
        po = self._po(origin="%s, OTHER-SO" % so.name, confirm=True)
        klass, _resolved = self.Transaction._classify_po_origin(po)
        self.assertEqual(klass, "ORIGIN_MULTIPLE")
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "name": so.name,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "detected",
                "is_uat_fixture": True,
            }
        )
        self.assertFalse(tx._has_confirmed_sale_po_relation())
        self.assertFalse(tx.action_auto_confirm_strong_trace())

    def test_03_cross_company_denied(self):
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) < 2:
            self.skipTest("need 2 companies")
        so = self._so()
        other = companies.filtered(lambda c: c.id != so.company_id.id)[:1]
        po = self.env["purchase.order"].with_company(other).create(
            {
                "partner_id": self.vendor.id,
                "company_id": other.id,
                "origin": so.name,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": 400,
                        },
                    )
                ],
            }
        )
        klass, _r = self.Transaction._classify_po_origin(po)
        self.assertEqual(klass, "ORIGIN_CROSS_COMPANY")

    def test_04_multi_po_same_so(self):
        so = self._so()
        po1 = self._po(origin=so.name)
        po2 = self._po(origin=so.name)
        tx = self.Transaction.find_or_create_canonical_transaction(
            sale_order=so,
            vals={
                "company_id": so.company_id.id,
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
                "state": "detected",
                "link_mode": "automatic",
            },
        )
        self.assertEqual(len(tx.purchase_order_ids), 2)
        tx.action_auto_confirm_strong_trace()
        self.assertEqual(tx.state, "validated")

    def test_05_no_fake_sale_line_id_on_backfill(self):
        so = self._so()
        po = self._po(origin=so.name)
        self.assertFalse(po.order_line.sale_line_id)
        self.Transaction.action_backfill_origin_sale_po_relations(
            dry_run=False, sale_order_ids=so.ids, purchase_order_ids=po.ids
        )
        po.invalidate_recordset()
        self.assertFalse(po.order_line.sale_line_id)
        tx = self.Transaction.search([("sale_order_ids", "in", so.ids)], limit=1)
        self.assertTrue(tx)
        self.assertIn(tx.state, ("validated", "approved", "closed"))

    def test_06_backfill_idempotent(self):
        so = self._so()
        po = self._po(origin=so.name)
        self.Transaction.action_backfill_origin_sale_po_relations(
            dry_run=False, sale_order_ids=so.ids, purchase_order_ids=po.ids
        )
        n_tx = self.Transaction.search_count([("sale_order_ids", "in", so.ids)])
        s2 = self.Transaction.action_backfill_origin_sale_po_relations(
            dry_run=False, sale_order_ids=so.ids, purchase_order_ids=po.ids
        )
        self.assertEqual(
            self.Transaction.search_count([("sale_order_ids", "in", so.ids)]), n_tx
        )
        self.assertEqual(s2.get("SAFE_CREATE_MTX", 0), 0)

    def test_07_cancelled_po_excluded_from_committed(self):
        so = self._so()
        po = self._po(origin=so.name)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "detected",
                "is_uat_fixture": True,
            }
        )
        tx.action_auto_confirm_strong_trace()
        po.write({"state": "cancel"})
        stage, _badge = tx._cost_document_stage()
        self.assertNotEqual(stage, "committed")
