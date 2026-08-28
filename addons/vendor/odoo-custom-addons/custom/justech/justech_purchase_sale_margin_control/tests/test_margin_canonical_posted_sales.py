# -*- coding: utf-8 -*-
"""19.0.8.20.0 — Factura posted canónica + costo de inventario atribuible."""
import zipfile
from io import BytesIO

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCanonicalPostedSales(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "CANON Cliente", "customer_rank": 1}
        )
        cls.customer_b = cls.env["res.partner"].create(
            {"name": "CANON Cliente B", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "CANON Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "CANON Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 1000,
                "standard_price": 200,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "CANON Product B",
                "type": "consu",
                "is_storable": True,
                "list_price": 500,
                "standard_price": 100,
            }
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.Canon = cls.env["purchase.sale.canonical.sale.service"]
        cls.Inv = cls.env["purchase.sale.inventory.cost.service"]

    def _so(self, partner=None, product=None, qty=1, price=1000):
        so = self.env["sale.order"].create(
            {
                "partner_id": (partner or self.customer).id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": (product or self.product).id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _out_invoice(self, so, qty=None, price=None, product=None):
        line = so.order_line[:1]
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
                            "product_id": (product or line.product_id).id,
                            "quantity": qty if qty is not None else line.product_uom_qty,
                            "price_unit": price if price is not None else line.price_unit,
                            "sale_line_ids": [(6, 0, line.ids)],
                            "name": (product or line.product_id).name,
                        },
                    )
                ],
            }
        )

    def _refund(self, partner, price=100):
        return self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": partner.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-20",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "name": "NC canónica",
                        },
                    )
                ],
            }
        )

    def _po_inventory(self, lines):
        """lines: list of (product, qty, price)."""
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_qty": qty,
                            "price_unit": price,
                            "cost_usage_type": "inventory_pending",
                        },
                    )
                    for product, qty, price in lines
                ],
            }
        )
        po.button_confirm()
        return po

    def _tx(self, so=None, sos=None, inv=None, po=None, date="2026-06-20", **extra):
        vals = {
            "company_id": self.company.id,
            "transaction_date": date,
            "state": "validated",
            "is_uat_fixture": True,
        }
        so_recs = sos or (so if so else self.env["sale.order"])
        if so_recs:
            if not hasattr(so_recs, "ids"):
                so_recs = so
            vals["customer_id"] = so_recs[:1].partner_id.id
            vals["sale_order_ids"] = [(6, 0, so_recs.ids)]
        if inv:
            vals["customer_invoice_ids"] = [(6, 0, inv.ids if hasattr(inv, "ids") else [inv.id])]
        if po:
            vals["purchase_order_ids"] = [(6, 0, po.ids if hasattr(po, "ids") else [po.id])]
            vals["supplier_ids"] = [(6, 0, [po[:1].partner_id.id])]
        vals.update(extra)
        return self.Transaction.with_context(allow_parallel_margin_tx=True).create(vals)

    def _report(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "only_uat": True,
            "show_complete": True,
            "show_sales_without_cost": False,
            "show_costs_without_sale": False,
            "show_incomplete": False,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def _blocks(self, report):
        return report._iter_sale_blocks()

    def _sales_untaxed(self, report):
        return round(sum(b["sale"]["untaxed"] for b in self._blocks(report)), 2)

    def test_01_estimated_without_invoice(self):
        so = self._so(price=500)
        po = self._po_inventory([(self.product, 1, 200)])
        tx = self._tx(so=so, po=po)
        sale = self.Report._sale_financials(tx)
        self.assertTrue(sale["is_estimated"])
        self.assertFalse(sale.get("is_superseded"))
        r = self._report()
        blocks = [b for b in self._blocks(r) if so in b["txs"].mapped("sale_order_ids")]
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0]["sale"]["is_estimated"])
        self.assertAlmostEqual(blocks[0]["sale"]["untaxed"], 500.0, places=2)

    def test_02_posted_invoice_replaces_estimated(self):
        so = self._so(price=800)
        inv = self._out_invoice(so, price=800)
        po = self._po_inventory([(self.product, 1, 200)])
        hub = self._tx(so=so, po=po, date="2026-05-01")
        inv_tx = self._tx(so=so, inv=inv, po=po, date="2026-06-15")
        self.assertTrue(self.Canon.is_superseded_estimated(hub))
        self.assertFalse(self.Canon.is_superseded_estimated(inv_tx))
        r = self._report()
        blocks = [b for b in self._blocks(r) if so in b["txs"].mapped("sale_order_ids")]
        self.assertEqual(len(blocks), 1)
        self.assertFalse(blocks[0]["sale"]["is_estimated"])
        self.assertAlmostEqual(blocks[0]["sale"]["untaxed"], inv.amount_untaxed, places=2)
        self.assertNotIn(hub, blocks[0]["txs"])

    def test_03_two_invoices_same_so_are_summed(self):
        so = self._so(qty=2, price=400)
        inv1 = self._out_invoice(so, qty=1, price=400)
        inv2 = self._out_invoice(so, qty=1, price=400)
        po = self._po_inventory([(self.product, 2, 100)])
        tx = self._tx(so=so, inv=inv1 | inv2, po=po)
        sale = self.Report._sale_financials(tx)
        self.assertAlmostEqual(
            sale["untaxed"], inv1.amount_untaxed + inv2.amount_untaxed, places=2
        )
        r = self._report()
        blocks = [b for b in self._blocks(r) if tx in b["txs"]]
        self.assertEqual(len(blocks), 1)
        self.assertAlmostEqual(
            blocks[0]["sale"]["untaxed"],
            inv1.amount_untaxed + inv2.amount_untaxed,
            places=2,
        )

    def test_04_invoice_plus_refund_nets(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        refund = self._refund(so.partner_id, price=150)
        po = self._po_inventory([(self.product, 1, 200)])
        tx = self._tx(so=so, inv=inv, po=po)
        tx.write({"customer_invoice_ids": [(4, refund.id)]})
        sale = self.Report._sale_financials(tx)
        self.assertAlmostEqual(
            sale["untaxed"], inv.amount_untaxed - refund.amount_untaxed, places=2
        )

    def test_05_hub_estimated_plus_invoice_mtx_shows_invoice(self):
        so_a = self._so(self.customer, self.product, 1, 8137.17)
        so_b = self._so(self.customer_b, self.product_b, 1, 1703.22)
        inv_a = self._out_invoice(so_a, price=8137.17)
        inv_b = self._out_invoice(so_b, price=1703.22)
        po = self._po_inventory(
            [(self.product, 1, 4027.04), (self.product_b, 1, 316.6)]
        )
        hub = self._tx(sos=so_a | so_b, po=po, date="2026-03-23")
        tx_a = self._tx(so=so_a, inv=inv_a, po=po, date="2026-05-12")
        tx_b = self._tx(so=so_b, inv=inv_b, po=po, date="2026-03-26")
        r = self._report()
        amounts = sorted(
            round(b["sale"]["untaxed"], 2)
            for b in self._blocks(r)
            if so_a in b["txs"].mapped("sale_order_ids")
            or so_b in b["txs"].mapped("sale_order_ids")
        )
        expected = sorted(
            [round(inv_a.amount_untaxed, 2), round(inv_b.amount_untaxed, 2)]
        )
        self.assertEqual(amounts, expected)
        self.assertFalse(
            any(b["sale"]["is_estimated"] and hub in b["txs"] for b in self._blocks(r))
        )
        self.assertAlmostEqual(sum(amounts), sum(expected), places=2)

    def test_06_sibling_hub_cost_attributed_to_invoice(self):
        so = self._so(price=6398)
        inv = self._out_invoice(so, price=6398)
        po = self._po_inventory([(self.product, 15, 938.88)])
        so.order_line[:1].write({"product_uom_qty": 15, "price_unit": 426.5333})
        inv.invoice_line_ids[:1].write({"quantity": 15})
        hub = self._tx(so=so, po=po, date="2026-06-01")
        inv_tx = self._tx(so=so, inv=inv, date="2026-07-09")  # PO only on hub
        self.assertFalse(inv_tx.purchase_order_ids)
        r = self._report()
        blocks = [
            b
            for b in self._blocks(r)
            if so in b["txs"].mapped("sale_order_ids")
        ]
        self.assertEqual(len(blocks), 1)
        self.assertFalse(blocks[0]["sale"]["is_estimated"])
        self.assertAlmostEqual(blocks[0]["cost_untaxed"], 15 * 938.88, places=2)
        self.assertTrue(r._op_included(r._operation_summary(inv_tx)))

    def test_07_complete_evaluated_at_canonical_sale(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po_inventory([(self.product, 1, 200)])
        self._tx(so=so, po=po, date="2026-01-01")
        inv_tx = self._tx(so=so, inv=inv, date="2026-02-01")
        r = self._report(show_complete=True)
        costs = r._cost_rows(inv_tx)
        self.assertTrue(any(c.get("include_in_margin") for c in costs))
        op = r._operation_summary(inv_tx)
        self.assertTrue(r._op_included(op))
        blocks = [b for b in self._blocks(r) if inv_tx in b["txs"] or so in b["txs"].mapped("sale_order_ids")]
        self.assertEqual(len(blocks), 1)
        self.assertFalse(blocks[0].get("incomplete_sale_only"))

    def test_08_p00004_pattern(self):
        so_palmar = self._so(self.customer, self.product, 1, 8137.17)
        so_midas = self._so(self.customer_b, self.product_b, 2, 851.61)
        inv_p = self._out_invoice(so_palmar, price=8137.17)
        inv_m = self._out_invoice(so_midas, qty=2, price=851.61)
        po = self._po_inventory(
            [(self.product, 1, 4027.04), (self.product_b, 1, 316.6)]
        )
        hub = self._tx(sos=so_palmar | so_midas, po=po, date="2026-03-23")
        tx_p = self._tx(so=so_palmar, inv=inv_p, po=po, date="2026-05-12")
        tx_m = self._tx(so=so_midas, inv=inv_m, po=po, date="2026-03-26")
        r = self._report()
        ours = [
            b
            for b in self._blocks(r)
            if so_palmar in b["txs"].mapped("sale_order_ids")
            or so_midas in b["txs"].mapped("sale_order_ids")
        ]
        self.assertEqual(len(ours), 2)
        palmar = [b for b in ours if so_palmar in b["txs"].mapped("sale_order_ids")][0]
        midas = [b for b in ours if so_midas in b["txs"].mapped("sale_order_ids")][0]
        self.assertAlmostEqual(palmar["sale"]["untaxed"], inv_p.amount_untaxed, places=2)
        self.assertAlmostEqual(midas["sale"]["untaxed"], inv_m.amount_untaxed, places=2)
        self.assertAlmostEqual(palmar["cost_untaxed"], 4027.04, places=2)
        self.assertAlmostEqual(midas["cost_untaxed"], 316.6, places=2)
        self.assertAlmostEqual(
            palmar["cost_untaxed"] + midas["cost_untaxed"], 4343.64, places=2
        )
        self.assertNotIn(hub, palmar["txs"] | midas["txs"])

    def test_09_p00130_pattern(self):
        jumbo = self.product
        pre = self.product_b
        multi = self.env["product.product"].create(
            {
                "name": "CANON Multifold",
                "type": "consu",
                "is_storable": True,
                "list_price": 1100,
                "standard_price": 938.88,
            }
        )
        so_farm = self._so(self.customer, jumbo, 25, 500)
        so_farm.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": pre.id,
                            "product_uom_qty": 17,
                            "price_unit": 500,
                        },
                    )
                ]
            }
        )
        so_esc = self._so(self.customer_b, multi, 15, 426.5333)
        inv_f = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so_farm.partner_id.id,
                "company_id": self.company.id,
                "invoice_date": "2026-07-13",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": jumbo.id,
                            "quantity": 25,
                            "price_unit": 500,
                            "sale_line_ids": [(6, 0, so_farm.order_line.filtered(lambda l: l.product_id == jumbo).ids)],
                            "name": jumbo.name,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": pre.id,
                            "quantity": 17,
                            "price_unit": 850,
                            "sale_line_ids": [(6, 0, so_farm.order_line.filtered(lambda l: l.product_id == pre).ids)],
                            "name": pre.name,
                        },
                    ),
                ],
            }
        )
        inv_e = self._out_invoice(so_esc, qty=15, price=426.5333, product=multi)
        po = self._po_inventory(
            [(jumbo, 50, 500.0), (pre, 20, 426.4), (multi, 15, 938.88)]
        )
        hub = self._tx(sos=so_farm | so_esc, po=po, date="2026-06-16")
        tx_e = self._tx(so=so_esc, inv=inv_e, po=po, date="2026-07-09")
        tx_f = self._tx(so=so_farm, inv=inv_f, po=po, date="2026-07-13")
        r = self._report()
        ours = [
            b
            for b in self._blocks(r)
            if so_farm in b["txs"].mapped("sale_order_ids")
            or so_esc in b["txs"].mapped("sale_order_ids")
        ]
        self.assertEqual(len(ours), 2)
        esc = [b for b in ours if so_esc in b["txs"].mapped("sale_order_ids")][0]
        farm = [b for b in ours if so_farm in b["txs"].mapped("sale_order_ids")][0]
        self.assertAlmostEqual(esc["sale"]["untaxed"], inv_e.amount_untaxed, places=2)
        self.assertAlmostEqual(farm["sale"]["untaxed"], inv_f.amount_untaxed, places=2)
        self.assertAlmostEqual(esc["cost_untaxed"], 14083.20, places=2)
        self.assertAlmostEqual(farm["cost_untaxed"], 19748.80, places=2)
        self.assertFalse(esc["sale"]["is_estimated"])
        self.assertFalse(farm["sale"]["is_estimated"])
        self.assertNotIn(hub, esc["txs"] | farm["txs"])

    def test_10_no_duplicate_sale(self):
        so = self._so(price=3225)
        inv = self._out_invoice(so, price=3225)
        po = self._po_inventory([(self.product, 1, 2382.75)])
        est = self._tx(so=so, po=po, date="2026-05-22")
        posted = self._tx(so=so, inv=inv, po=po, date="2026-05-25")
        r = self._report(show_complete=True, show_sales_without_cost=True, show_incomplete=True)
        blocks = [
            b for b in self._blocks(r) if so in b["txs"].mapped("sale_order_ids")
        ]
        self.assertEqual(len(blocks), 1)
        self.assertAlmostEqual(blocks[0]["sale"]["untaxed"], inv.amount_untaxed, places=2)
        self.assertFalse(blocks[0]["sale"]["is_estimated"])

    def test_11_no_duplicate_cost(self):
        so = self._so(price=3225)
        inv = self._out_invoice(so, price=3225)
        po = self._po_inventory([(self.product, 1, 2382.75)])
        self._tx(so=so, po=po, date="2026-05-22")
        self._tx(so=so, inv=inv, po=po, date="2026-05-25")
        r = self._report(show_complete=True, show_incomplete=True)
        blocks = [
            b for b in self._blocks(r) if so in b["txs"].mapped("sale_order_ids")
        ]
        self.assertEqual(len(blocks), 1)
        self.assertAlmostEqual(blocks[0]["cost_untaxed"], 2382.75, places=2)

    def test_12_inventory_still_by_qty(self):
        po = self._po_inventory([(self.product, 100, 1000)])
        so_a = self._so(self.customer, self.product, 10, 1150)
        so_b = self._so(self.customer_b, self.product, 20, 1150)
        tx_a = self._tx(so=so_a, po=po, date="2026-06-01")
        tx_b = self._tx(so=so_b, po=po, date="2026-06-02")
        r = self._report()
        ledger = {}
        op_a = r._operation_summary(tx_a, allocation_ledger=ledger)
        op_b = r._operation_summary(tx_b, allocation_ledger=ledger)
        self.assertAlmostEqual(op_a["cost_untaxed"], 10000.0, places=2)
        self.assertAlmostEqual(op_b["cost_untaxed"], 20000.0, places=2)
        self.assertLess(op_a["cost_untaxed"] + op_b["cost_untaxed"], 100000.0)

    def test_13_multi_scope_filters(self):
        so = self._so(price=500)
        inv = self._out_invoice(so, price=500)
        sale_only = self._tx(so=so, inv=inv)
        r_complete = self._report(show_complete=True)
        self.assertFalse(
            any(sale_only in b["txs"] for b in self._blocks(r_complete))
        )
        r_sales = self._report(show_complete=False, show_sales_without_cost=True)
        self.assertTrue(any(sale_only in b["txs"] for b in self._blocks(r_sales)))

    def test_14_preview_same_dataset(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po_inventory([(self.product, 1, 200)])
        self._tx(so=so, inv=inv, po=po)
        r = self._report()
        n1 = len(r._general_summary().get("operations") or [])
        action = r.action_preview()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-html")
        n2 = len(r._general_summary().get("operations") or [])
        self.assertEqual(n1, n2)

    def test_15_pdf_xlsx_same_count(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po_inventory([(self.product, 1, 200)])
        self._tx(so=so, inv=inv, po=po)
        r = self._report()
        n_pdf = len(r._general_summary().get("operations") or [])
        data = r._generate_xlsx_bytes()
        self.assertTrue(data)
        n_x = len(r._general_summary().get("operations") or [])
        self.assertEqual(n_pdf, n_x)
        zf = zipfile.ZipFile(BytesIO(data))
        self.assertTrue(zf.namelist())

    def test_16_canonical_mtx_api_intact(self):
        so = self._so(price=100)
        tx = self.Transaction.find_or_create_canonical_transaction(sale_order=so)
        again = self.Transaction.find_canonical_for_sale(so)
        self.assertEqual(tx, again)

    def test_17_cross_trace_still_resolves(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        po = self._po_inventory([(self.product, 1, 200)])
        tx = self._tx(so=so, inv=inv, po=po)
        self.assertIn(so, tx.sale_order_ids)
        self.assertIn(inv, tx.customer_invoice_ids)
        self.assertIn(po, tx.purchase_order_ids)

    def test_18_cxp_still_from_vendor_bill(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
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
                            "price_unit": 200,
                            "cost_usage_type": "resale_direct",
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "company_id": self.company.id,
                "invoice_date": "2026-06-10",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 200,
                            "purchase_line_id": po.order_line[:1].id,
                            "name": self.product.name,
                        },
                    )
                ],
            }
        )
        self._tx(so=so, inv=inv, po=po)
        tx = self.Transaction.search(
            [("sale_order_ids", "in", so.id), ("is_uat_fixture", "=", True)], limit=1
        )
        tx.write({"vendor_bill_ids": [(6, 0, [bill.id])]})
        r = self._report()
        grand = r._general_summary()
        vendors = {row.get("vendor") for row in grand.get("cxp_rows") or []}
        self.assertIn(self.vendor.name, vendors)

    def test_19_usd_dop_conversion_helper_intact(self):
        r = self._report()
        dop = self.company.currency_id
        converted, rate, ok, _date = r._convert_amount(100.0, dop, dop, self.company, "2026-06-01")
        self.assertTrue(ok)
        self.assertAlmostEqual(converted, 100.0, places=2)
        self.assertEqual(rate, 1.0)

    def test_20_credit_note_sign_in_blocks(self):
        so = self._so(price=1000)
        inv = self._out_invoice(so, price=1000)
        refund = self._refund(so.partner_id, 200)
        po = self._po_inventory([(self.product, 1, 200)])
        tx = self._tx(so=so, inv=inv, po=po)
        tx.write({"customer_invoice_ids": [(4, refund.id)]})
        r = self._report()
        blocks = [b for b in self._blocks(r) if tx in b["txs"]]
        self.assertEqual(len(blocks), 1)
        self.assertAlmostEqual(
            blocks[0]["sale"]["untaxed"],
            inv.amount_untaxed - refund.amount_untaxed,
            places=2,
        )
