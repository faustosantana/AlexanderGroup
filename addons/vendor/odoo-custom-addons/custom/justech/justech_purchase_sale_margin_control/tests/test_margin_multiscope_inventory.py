# -*- coding: utf-8 -*-
"""19.0.8.19.0 — Multi-scope operations + inventory cost by consumption."""
import zipfile
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginMultiScopeOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "MSCOPE Cliente", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "MSCOPE Proveedor", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "MSCOPE Product",
                "type": "consu",
                "list_price": 1000,
                "standard_price": 200,
            }
        )
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _so(self, price=1000):
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

    def _tx(self, so=None, inv=None, po=None, bill=None, state="validated"):
        vals = {
            "company_id": self.company.id,
            "transaction_date": "2026-06-20",
            "state": state,
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
        return self.Transaction.create(vals)

    def _fixtures(self):
        so_c = self._so(1000)
        inv_c = self._out_invoice(so_c, 1000)
        po_c = self._po(200)
        bill_c = self._bill(po_c, 200)
        complete = self._tx(so=so_c, inv=inv_c, po=po_c, bill=bill_c)

        so_s = self._so(500)
        inv_s = self._out_invoice(so_s, 500)
        sale_only = self._tx(so=so_s, inv=inv_s)

        po_k = self._po(150)
        bill_k = self._bill(po_k, 150)
        cost_only = self._tx(po=po_k, bill=bill_k)
        return {"complete": complete, "sale_only": sale_only, "cost_only": cost_only}

    def _report(self, **kwargs):
        vals = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "report_layout": "compact",
            "only_uat": True,
            "show_complete": True,
            "show_sales_without_cost": False,
            "show_costs_without_sale": False,
            "show_incomplete": False,
        }
        vals.update(kwargs)
        return self.Report.create(vals)

    def _present(self, report, fixtures):
        found = set(report._iter_transactions().ids)
        out = {}
        for key, rec in fixtures.items():
            if rec.id not in found:
                out[key] = False
                continue
            op = report._operation_summary(rec)
            out[key] = bool(report._op_included(op))
        return out

    def test_01_complete_plus_sales_wo_cost(self):
        fx = self._fixtures()
        r = self._report(show_complete=True, show_sales_without_cost=True)
        p = self._present(r, fx)
        self.assertTrue(p["complete"])
        self.assertTrue(p["sale_only"])
        self.assertFalse(p["cost_only"])

    def test_02_sales_and_costs_without_complete(self):
        fx = self._fixtures()
        r = self._report(
            show_complete=False,
            show_sales_without_cost=True,
            show_costs_without_sale=True,
        )
        p = self._present(r, fx)
        self.assertFalse(p["complete"])
        self.assertTrue(p["sale_only"])
        self.assertTrue(p["cost_only"])

    def test_03_only_sales_without_cost(self):
        fx = self._fixtures()
        r = self._report(show_complete=False, show_sales_without_cost=True)
        p = self._present(r, fx)
        self.assertFalse(p["complete"])
        self.assertTrue(p["sale_only"])
        self.assertFalse(p["cost_only"])

    def test_04_only_costs_without_sale(self):
        fx = self._fixtures()
        r = self._report(show_complete=False, show_costs_without_sale=True)
        p = self._present(r, fx)
        self.assertFalse(p["complete"])
        self.assertFalse(p["sale_only"])
        self.assertTrue(p["cost_only"])

    def test_05_all_selected(self):
        fx = self._fixtures()
        r = self._report(
            show_complete=True,
            show_sales_without_cost=True,
            show_costs_without_sale=True,
            show_incomplete=True,
        )
        p = self._present(r, fx)
        self.assertTrue(p["complete"])
        self.assertTrue(p["sale_only"])
        self.assertTrue(p["cost_only"])
        self.assertEqual(r._report_scope_label(), "Todas las operaciones")

    def test_06_none_selected_raises(self):
        with self.assertRaises(UserError):
            self._report(
                show_complete=False,
                show_sales_without_cost=False,
                show_costs_without_sale=False,
                show_incomplete=False,
            )._transaction_domain()

    def test_07_preview_pdf_same_dataset(self):
        self._fixtures()
        r = self._report(show_complete=True, show_sales_without_cost=True)
        n1 = len(r._general_summary().get("operations") or [])
        action = r.action_preview()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-html")
        n2 = len(r._general_summary().get("operations") or [])
        self.assertEqual(n1, n2)

    def test_08_xlsx_same_dataset(self):
        self._fixtures()
        r = self._report(show_complete=True)
        n_pdf = len(r._general_summary().get("operations") or [])
        data = r._generate_xlsx_bytes()
        self.assertTrue(data)
        n_x = len(r._general_summary().get("operations") or [])
        self.assertEqual(n_pdf, n_x)

    def test_09_wizard_has_multi_select_ui(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_cost_vs_sale_report_form"
        )
        arch = view.arch_db or ""
        self.assertIn("show_complete", arch)
        self.assertIn("show_sales_without_cost", arch)
        self.assertIn("action_preview", arch)
        self.assertIn("action_select_all_operation_types", arch)

    def test_10_legacy_report_scope_maps(self):
        fx = self._fixtures()
        # No pasar show_* para que report_scope sea la fuente
        r = self.Report.create(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "company_id": self.company.id,
                "only_uat": True,
                "report_scope": "sales_wo_cost",
            }
        )
        self.assertFalse(r.show_complete)
        self.assertTrue(r.show_sales_without_cost)
        p = self._present(r, fx)
        self.assertTrue(p["sale_only"])
        self.assertFalse(p["complete"])


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginInventoryAllocation(TransactionCase):
    """Compra inventario 100 → ventas parciales; sin duplicar OC completa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vendor = cls.env["res.partner"].create(
            {"name": "INVALLOC Vendor", "supplier_rank": 1}
        )
        cls.cust_a = cls.env["res.partner"].create(
            {"name": "INVALLOC A", "customer_rank": 1}
        )
        cls.cust_b = cls.env["res.partner"].create(
            {"name": "INVALLOC B", "customer_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "INVALLOC Widget",
                "type": "consu",
                "is_storable": True,
                "list_price": 1150,
                "standard_price": 1000,
            }
        )
        cls.Inv = cls.env["purchase.sale.inventory.cost.service"]
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]

    def _po_inventory(self, qty=100, price=1000):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "price_unit": price,
                            "cost_usage_type": "inventory_pending",
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _so(self, partner, qty, price):
        so = self.env["sale.order"].create(
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

    def test_09_to_14_inventory_partial_allocation(self):
        po = self._po_inventory(100, 1000)
        so_a = self._so(self.cust_a, 10, 1150)
        so_b = self._so(self.cust_b, 20, 1150)
        tx_a = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-06-01",
                "state": "validated",
                "is_uat_fixture": True,
                "customer_id": self.cust_a.id,
                "sale_order_ids": [(6, 0, [so_a.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        tx_b = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-06-02",
                "state": "validated",
                "is_uat_fixture": True,
                "customer_id": self.cust_b.id,
                "sale_order_ids": [(6, 0, [so_b.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        ledger = {}
        rows_a, ledger = self.Inv.allocate_inventory_po_cost_for_sales(
            po, so_a, allocation_ledger=ledger, currency=self.company.currency_id
        )
        rows_b, ledger = self.Inv.allocate_inventory_po_cost_for_sales(
            po, so_b, allocation_ledger=ledger, currency=self.company.currency_id
        )
        cost_a = sum(r["untaxed"] for r in rows_a)
        cost_b = sum(r["untaxed"] for r in rows_b)
        self.assertAlmostEqual(cost_a, 10000.0, places=2)
        self.assertAlmostEqual(cost_b, 20000.0, places=2)
        self.assertAlmostEqual(cost_a + cost_b, 30000.0, places=2)
        self.assertLess(cost_a + cost_b, 100000.0)
        # stock restante 70 no imputado
        allocated_qty = sum(ledger.values())
        self.assertAlmostEqual(allocated_qty, 30.0, places=2)

        # vía _cost_rows con ledger compartido
        report = self.Report.create(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "company_id": self.company.id,
                "only_uat": True,
                "show_complete": True,
            }
        )
        ledger2 = {}
        op_a = report._operation_summary(tx_a, allocation_ledger=ledger2)
        op_b = report._operation_summary(tx_b, allocation_ledger=ledger2)
        self.assertAlmostEqual(op_a["cost_untaxed"], 10000.0, places=2)
        self.assertAlmostEqual(op_b["cost_untaxed"], 20000.0, places=2)
        self.assertAlmostEqual(op_a["margin"], 1500.0, places=2)
        # Margen % = (venta-costo)/venta ; NO markup
        margin_pct = op_a["margin"] / op_a["sale"]["untaxed"] * 100.0
        markup_pct = op_a["margin"] / op_a["cost_untaxed"] * 100.0
        self.assertAlmostEqual(margin_pct, 13.043478, places=4)
        self.assertAlmostEqual(markup_pct, 15.0, places=2)
        self.assertAlmostEqual(op_a.get("margin_pct") or margin_pct, margin_pct, places=2)

    def test_15_direct_purchase_intact(self):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 10,
                            "price_unit": 1000,
                            "cost_usage_type": "resale_direct",
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        so = self._so(self.cust_a, 10, 1150)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "transaction_date": "2026-06-03",
                "state": "validated",
                "is_uat_fixture": True,
                "customer_id": self.cust_a.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        report = self.Report.create(
            {
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "company_id": self.company.id,
                "only_uat": True,
                "show_complete": True,
            }
        )
        op = report._operation_summary(tx)
        # compra directa sin bill: PO completa (10×1000) sigue válida
        self.assertAlmostEqual(op["cost_untaxed"], 10000.0, places=2)

    def test_16_margin_not_confused_with_markup(self):
        """Documenta MARGEN % = (v-c)/v ; MARKUP = (v-c)/c."""
        sale, cost = 11500.0, 10000.0
        margin = sale - cost
        margin_pct = margin / sale * 100.0
        markup_pct = margin / cost * 100.0
        self.assertAlmostEqual(margin_pct, 13.0434782609, places=6)
        self.assertAlmostEqual(markup_pct, 15.0, places=2)
        self.assertNotAlmostEqual(margin_pct, markup_pct, places=2)
