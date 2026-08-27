# -*- coding: utf-8 -*-
"""Freeze TODAS: categorías, sin duplicados, company/fecha, margen confirmado."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginAllScopeFreeze(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other = cls.env["res.company"].search(
            [("id", "!=", cls.company.id)], limit=1
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "ALLSCOPE Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "ALLSCOPE Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "ALLSCOPE Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 1000,
                "standard_price": 200,
            }
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self, price=1000, partner=None):
        so = self.env["sale.order"].create(
            {
                "partner_id": (partner or self.customer).id,
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

    def _inv(self, so, price=None):
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

    def _po(self, price=200):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": price,
                            "cost_usage_type": "resale_direct",
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

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

    def _tx(self, so=None, inv=None, po=None, bill=None, date="2026-06-20"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": date,
            "state": "validated",
            "is_uat_fixture": True,
        }
        if so:
            vals["customer_id"] = so.partner_id.id
            vals["sale_order_ids"] = [(6, 0, [so.id])]
        if inv:
            vals["customer_invoice_ids"] = [(6, 0, [inv.id])]
        if po:
            vals["purchase_order_ids"] = [(6, 0, [po.id])]
            vals["supplier_ids"] = [(6, 0, [po.partner_id.id])]
        if bill:
            vals["vendor_bill_ids"] = [(6, 0, [bill.id])]
        return self.Transaction.with_context(allow_parallel_margin_tx=True).create(vals)

    def _todas(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "only_uat": True,
            "show_complete": True,
            "show_sales_without_cost": True,
            "show_costs_without_sale": True,
            "show_incomplete": True,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def test_01_todas_categories_exclusive(self):
        so_c = self._so(1000)
        inv_c = self._inv(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)

        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        self._tx(so=so_s, inv=inv_s)

        so_e = self._so(300)
        self._tx(so=so_e)

        po_k = self._po(150)
        bill_k = self._bill(po_k, 150)
        self._tx(po=po_k, bill=bill_k)

        r = self._todas()
        g = r._general_summary()
        cats = g["category_totals"]
        self.assertGreaterEqual(cats["OPERACIONES_COMPLETAS"]["count"], 1)
        self.assertGreaterEqual(cats["VENTAS_SIN_COSTOS"]["count"], 1)
        self.assertGreaterEqual(cats["ESTIMADAS_SIN_FACTURAR"]["count"], 1)
        self.assertGreaterEqual(cats["COSTOS_SIN_VENTA"]["count"], 1)
        counted = sum(c["count"] for c in cats.values())
        self.assertEqual(counted, len(g["operations"]))
        cats_on_blocks = {b.get("scope_category") for b in g["operations"]}
        self.assertTrue(cats_on_blocks <= set(cats))

    def test_02_no_duplicate_posted_invoice(self):
        so = self._so(800)
        inv = self._inv(so, 800)
        po = self._po(200)
        # Hub estimado y MTX de factura pueden compartir OC, no la misma bill.
        self._tx(so=so, po=po, date="2026-05-01")
        self._tx(so=so, inv=inv, po=po, date="2026-06-15")
        r = self._todas()
        seen = []
        for b in r._iter_sale_blocks():
            for m in b["sale"].get("moves") or []:
                seen.append(m.id)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(seen.count(inv.id), 1)

    def test_03_no_duplicate_estimated_once_invoiced(self):
        so = self._so(800)
        inv = self._inv(so, 800)
        po = self._po(200)
        hub = self._tx(so=so, po=po, date="2026-05-01")
        self._tx(so=so, inv=inv, po=po, date="2026-06-15")
        r = self._todas()
        est = [
            b
            for b in r._iter_sale_blocks()
            if hub in b["txs"] and b["sale"].get("is_estimated")
        ]
        self.assertFalse(est)

    def test_04_company_scope(self):
        so = self._so(1000)
        inv = self._inv(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        self._tx(so=so, inv=inv, po=po, bill=bill)
        r = self._todas()
        companies = {b["company"].name for b in r._iter_sale_blocks()}
        self.assertEqual(companies, {self.company.name})

    def test_05_date_scope(self):
        so = self._so(1000)
        inv = self._inv(so, 1000)
        po = self._po(200)
        bill = self._bill(po, 200)
        inside = self._tx(so=so, inv=inv, po=po, bill=bill, date="2026-06-20")
        so2 = self._so(400)
        inv2 = self._inv(so2, 400)
        outside = self._tx(so=so2, inv=inv2, date="2025-12-31")
        r = self._todas(date_from="2026-01-01", date_to="2026-12-31")
        txs = {tx.id for b in r._iter_sale_blocks() for tx in b["txs"]}
        self.assertIn(inside.id, txs)
        self.assertNotIn(outside.id, txs)

    def test_06_confirmed_margin_excludes_sales_without_cost(self):
        so_c = self._so(1000)
        inv_c = self._inv(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)
        so_s = self._so(5000)
        inv_s = self._inv(so_s, 5000)
        self._tx(so=so_s, inv=inv_s)
        r = self._todas()
        g = r._general_summary()
        cats = g["category_totals"]
        row = g["by_currency_rows"][0]
        self.assertAlmostEqual(row["margin"], cats["OPERACIONES_COMPLETAS"]["margin"], places=2)
        self.assertGreater(cats["VENTAS_SIN_COSTOS"]["sale"], 0.0)
        self.assertAlmostEqual(row.get("sale_without_cost") or 0.0, cats["VENTAS_SIN_COSTOS"]["sale"], places=2)
        mixed_pct = row["margin"] / row["sale_untaxed"] * 100.0
        confirmed_pct = row["margin"] / row["sale_confirmed"] * 100.0
        self.assertAlmostEqual(row["margin_pct"], confirmed_pct, places=2)
        self.assertNotAlmostEqual(mixed_pct, confirmed_pct, places=2)

    def test_07_cost_without_sale_does_not_change_margin(self):
        so_c = self._so(1000)
        inv_c = self._inv(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)
        r0 = self._todas(show_costs_without_sale=False, show_incomplete=False)
        g0 = r0._general_summary()
        m0 = list(g0["by_currency"].values())[0]["margin"]
        po_k = self._po(999)
        bill_k = self._bill(po_k, 999)
        self._tx(po=po_k, bill=bill_k)
        r1 = self._todas()
        g1 = r1._general_summary()
        m1 = list(g1["by_currency"].values())[0]["margin"]
        self.assertAlmostEqual(m0, m1, places=2)
        self.assertGreaterEqual(g1["category_totals"]["COSTOS_SIN_VENTA"]["count"], 1)

    def test_08_category_summary_sums_sales(self):
        so_c = self._so(1000)
        inv_c = self._inv(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)
        so_s = self._so(500)
        inv_s = self._inv(so_s, 500)
        self._tx(so=so_s, inv=inv_s)
        so_e = self._so(300)
        self._tx(so=so_e)
        r = self._todas()
        g = r._general_summary()
        cats = g["category_totals"]
        summed = sum(c["sale"] for c in cats.values())
        dop = list(g["by_currency"].values())[0]
        self.assertAlmostEqual(summed, dop["sale_untaxed"], places=2)
        self.assertAlmostEqual(
            cats["OPERACIONES_COMPLETAS"]["sale"] + cats["VENTAS_SIN_COSTOS"]["sale"] + cats["ESTIMADAS_SIN_FACTURAR"]["sale"],
            dop["sale_untaxed"],
            places=2,
        )
        row = [x for x in g["by_currency_rows"] if x.get("currency_id") == dop.get("currency_id") or True][0]
        self.assertAlmostEqual(row["margin_pct"], dop["margin"] / dop["sale_confirmed"] * 100.0, places=2)
