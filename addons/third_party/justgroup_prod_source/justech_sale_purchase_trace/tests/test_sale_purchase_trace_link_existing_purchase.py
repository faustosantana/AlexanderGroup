# -*- coding: utf-8 -*-
"""19.0.1.2.4 — Relacionar compra existente: OC + factura proveedor."""
from uuid import uuid4

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseLinkExistingPurchase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente LinkBill %s" % uuid4().hex[:6], "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Proveedor LinkBill", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Laptop LinkBill %s" % uuid4().hex[:6],
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 1000,
                "standard_price": 600,
            }
        )
        cls.expense = cls.env["account.account"].search(
            [
                ("account_type", "=", "expense"),
            ],
            limit=1,
        )

    def _so(self, qty=10, partner=None, product=None):
        product = product or self.product
        return self.env["sale.order"].create(
            {
                "partner_id": (partner or self.partner).id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": product.list_price,
                        },
                    )
                ],
            }
        )

    def _refresh(self, sol):
        sol.invalidate_recordset()
        sol._compute_justech_purchase_coverage()
        return sol

    def _po(self, qty=10, vendor=None, product=None):
        product = product or self.product
        return self.env["purchase.order"].create(
            {
                "partner_id": (vendor or self.vendor).id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": qty,
                            "price_unit": product.standard_price,
                            "product_uom_id": product.uom_id.id,
                        },
                    )
                ],
            }
        )

    def _vendor_bill(self, qty=10, price=600, product=None, vendor=None, refund=False):
        product = product or self.product
        line_vals = {
            "product_id": product.id,
            "name": product.display_name,
            "quantity": qty,
            "price_unit": price,
        }
        if self.expense:
            line_vals["account_id"] = self.expense.id
        move = self.env["account.move"].create(
            {
                "move_type": "in_refund" if refund else "in_invoice",
                "partner_id": (vendor or self.vendor).id,
                "company_id": self.company.id,
                "invoice_line_ids": [(0, 0, line_vals)],
            }
        )
        return move

    def _link_bill_wiz(self, so, bill_line, qty, amount=None, selected=True):
        sol = self._refresh(so.order_line.filtered(lambda l: not l.display_type)[:1])
        pending = sol.justech_qty_pending_purchase
        avail = bill_line._justech_bill_qty_available()
        amt_avail = bill_line._justech_bill_amount_available()
        if amount is None and qty and bill_line._justech_bill_qty_signed():
            amount = bill_line._justech_bill_amount_signed() * (
                qty / bill_line._justech_bill_qty_signed()
            )
        return self.env["justech.link.existing.po.wizard"].create(
            {
                "sale_order_id": so.id,
                "document_type": "vendor_bill",
                "bill_line_ids": [
                    (
                        0,
                        0,
                        {
                            "vendor_bill_line_id": bill_line.id,
                            "vendor_bill_id": bill_line.move_id.id,
                            "purchase_line_id": bill_line.purchase_line_id.id,
                            "product_id": bill_line.product_id.id,
                            "sale_line_id": sol.id,
                            "qty_bill": bill_line._justech_bill_qty_signed(),
                            "qty_available": avail,
                            "qty_to_assign": qty,
                            "amount_available": amt_avail,
                            "amount_to_assign": amount or 0.0,
                            "currency_id": bill_line.currency_id.id,
                            "selected": selected,
                            "snapshot_pending": pending,
                            "snapshot_available": avail,
                            "snapshot_amount_available": amt_avail,
                        },
                    )
                ],
            }
        )

    def test_01_po_full(self):
        so = self._so(10)
        po = self._po(10)
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so.order_line[0], 10)
        self.assertAlmostEqual(self._refresh(so.order_line[0]).justech_qty_pending_purchase, 0)

    def test_02_po_partial(self):
        so = self._so(10)
        po = self._po(10)
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so.order_line[0], 4)
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 4)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6)

    def test_03_vendor_bill_with_po(self):
        so = self._so(10)
        po = self._po(10)
        pol = po.order_line[0]
        # Simular AML con purchase_line_id (factura desde OC)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        aml.purchase_line_id = pol.id
        wiz = self._link_bill_wiz(so, aml, qty=4)
        wiz.action_confirm_link()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 4)
        # Cantidad parcial: puede splittear POL o usar assignment (sin sale_line_id directo).
        linked = (
            pol.sale_line_id == so.order_line[0]
            or bool(
                pol.justech_qty_assignment_ids.filtered(
                    lambda a: a.sale_line_id == so.order_line[0] and a.state == "active"
                )
            )
            or bool(
                po.order_line.filtered(lambda l: l.sale_line_id == so.order_line[0])
            )
        )
        self.assertTrue(linked)
        # No assignment paralelo para factura con POL
        assigns = self.env["justech.purchase.sale.qty.assignment"].search(
            [("vendor_bill_line_id", "=", aml.id), ("state", "=", "active")]
        )
        self.assertFalse(assigns)

    def test_04_vendor_bill_without_po(self):
        so = self._so(10)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        self.assertFalse(aml.purchase_line_id)
        debit_before = aml.debit
        credit_before = aml.credit
        residual_before = bill.amount_residual
        wiz = self._link_bill_wiz(so, aml, qty=4)
        wiz.action_confirm_link()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 4)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 6)
        aml.invalidate_recordset()
        bill.invalidate_recordset()
        self.assertAlmostEqual(aml.debit, debit_before)
        self.assertAlmostEqual(aml.credit, credit_before)
        self.assertAlmostEqual(bill.amount_residual, residual_before)

    def test_05_vendor_bill_partial_then_more(self):
        so = self._so(10)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        self._link_bill_wiz(so, aml, qty=6).action_confirm_link()
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 4)
        self._link_bill_wiz(so, aml, qty=4).action_confirm_link()
        sol = self._refresh(sol)
        self.assertAlmostEqual(sol.justech_qty_pending_purchase, 0)
        self.assertAlmostEqual(aml._justech_bill_qty_available(), 0)

    def test_06_vendor_bill_shared_two_sales(self):
        so_a = self._so(6)
        so_b = self._so(4)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        self._link_bill_wiz(so_a, aml, qty=6).action_confirm_link()
        self._link_bill_wiz(so_b, aml, qty=4).action_confirm_link()
        self.assertAlmostEqual(self._refresh(so_a.order_line[0]).justech_qty_purchased, 6)
        self.assertAlmostEqual(self._refresh(so_b.order_line[0]).justech_qty_purchased, 4)
        self.assertAlmostEqual(aml._justech_bill_qty_available(), 0)

    def test_07_over_qty_blocked(self):
        so = self._so(10)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        self._link_bill_wiz(so, aml, qty=6).action_confirm_link()
        with self.assertRaises(UserError) as err:
            self._link_bill_wiz(so, aml, qty=6).action_confirm_link()
        self.assertIn("4", str(err.exception))

    def test_08_over_amount_blocked(self):
        so = self._so(10)
        bill = self._vendor_bill(10, price=100)
        aml = bill.invoice_line_ids[0]
        wiz = self._link_bill_wiz(so, aml, qty=1, amount=9999)
        with self.assertRaises(UserError):
            wiz.action_confirm_link()

    def test_09_customer_invoice_excluded(self):
        so = self._so(5)
        out = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 5,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        vals = self.env["justech.link.existing.po.wizard"]._prepare_candidate_bill_lines_for(
            so
        )
        ids = {v["vendor_bill_line_id"] for v in vals}
        self.assertFalse(set(out.invoice_line_ids.ids) & ids)

    def test_10_cancelled_vendor_bill_excluded(self):
        # Isolate from Accounting Recovery SoD: grant the recovery group to the
        # test user so button_cancel can run. Does not change production rules.
        recovery = self.env.ref(
            "justech_accounting_recovery.group_accounting_recovery",
            raise_if_not_found=False,
        )
        if recovery and not self.env.user.has_group(
            "justech_accounting_recovery.group_accounting_recovery"
        ):
            self.env.user.sudo().write({"group_ids": [(4, recovery.id)]})
        so = self._so(5)
        bill = self._vendor_bill(5)
        bill.button_cancel()
        vals = self.env["justech.link.existing.po.wizard"]._prepare_candidate_bill_lines_for(
            so
        )
        ids = {v["vendor_bill_line_id"] for v in vals}
        self.assertNotIn(bill.invoice_line_ids.id, ids)

    def test_11_vendor_credit_note(self):
        so = self._so(10)
        bill = self._vendor_bill(10, price=600)
        aml = bill.invoice_line_ids[0]
        self._link_bill_wiz(so, aml, qty=10).action_confirm_link()
        cost_before = self._refresh(so.order_line[0]).justech_trace_cost
        refund = self._vendor_bill(2, price=600, refund=True)
        ram = refund.invoice_line_ids[0]
        self._link_bill_wiz(so, ram, qty=2).action_confirm_link()
        sol = self._refresh(so.order_line[0])
        # Purchased qty permanece (NC no suma cobertura de compra)
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)
        self.assertLess(sol.justech_trace_cost, cost_before)

    def test_12_other_company_blocked(self):
        # Crear factura en otra compañía exige diario/CoA; validamos el dominio
        # de compañía (equivalente funcional: nunca aparecen AML de otra co).
        other = self.env["res.company"].create({"name": "Otra Co LinkBill"})
        so = self._so(4)
        domain = self.env["account.move.line"]._justech_vendor_bill_line_domain(
            so.company_id, so.order_line.mapped("product_id")
        )
        self.assertIn(("company_id", "=", so.company_id.id), domain)
        self.assertNotEqual(so.company_id.id, other.id)
        bill_local = self._vendor_bill(4)
        vals = self.env["justech.link.existing.po.wizard"]._prepare_candidate_bill_lines_for(
            so
        )
        ids = {v["vendor_bill_line_id"] for v in vals}
        self.assertIn(bill_local.invoice_line_ids.id, ids)
        for aml_id in ids:
            aml = self.env["account.move.line"].browse(aml_id)
            self.assertEqual(aml.company_id, so.company_id)

    def test_13_vendor_filter(self):
        so = self._so(5)
        other_vendor = self.env["res.partner"].create(
            {"name": "Otro Prov", "supplier_rank": 1}
        )
        bill_ok = self._vendor_bill(5)
        bill_other = self._vendor_bill(5, vendor=other_vendor)
        vals = self.env["justech.link.existing.po.wizard"]._prepare_candidate_bill_lines_for(
            so, partner=self.vendor
        )
        ids = {v["vendor_bill_line_id"] for v in vals}
        self.assertIn(bill_ok.invoice_line_ids.id, ids)
        self.assertNotIn(bill_other.invoice_line_ids.id, ids)

    def test_14_partner_change_reloads(self):
        so = self._so(5)
        self._vendor_bill(5)
        wiz = self.env["justech.link.existing.po.wizard"].create(
            {
                "sale_order_id": so.id,
                "document_type": "vendor_bill",
                "partner_id": self.vendor.id,
            }
        )
        wiz._onchange_reload_candidates()
        self.assertTrue(wiz.bill_line_ids)
        other = self.env["res.partner"].create({"name": "X", "supplier_rank": 1})
        wiz.partner_id = other
        wiz._onchange_reload_candidates()
        self.assertFalse(wiz.bill_line_ids)

    def test_15_concurrency(self):
        so = self._so(10)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        stale = self._link_bill_wiz(so, aml, qty=4)
        self._link_bill_wiz(so, aml, qty=4).action_confirm_link()
        with self.assertRaises(UserError) as err:
            stale.action_confirm_link()
        self.assertIn("cambiaron", str(err.exception).lower())

    def test_16_multicurrency_keeps_doc_currency(self):
        usd = self.env.ref("base.USD")
        so = self._so(4)
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "currency_id": usd.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.display_name,
                            "quantity": 4,
                            "price_unit": 50,
                            "account_id": self.expense.id,
                        },
                    )
                ],
            }
        )
        aml = bill.invoice_line_ids[0]
        wiz = self._link_bill_wiz(so, aml, qty=4)
        wiz.action_confirm_link()
        assign = self.env["justech.purchase.sale.qty.assignment"].search(
            [("vendor_bill_line_id", "=", aml.id), ("state", "=", "active")], limit=1
        )
        self.assertEqual(assign.currency_id, usd)
        self.assertEqual(bill.currency_id, usd)

    def test_17_customer_invoice_via_sol(self):
        so = self._so(3)
        so.order_line.product_id.invoice_policy = "order"
        so.with_context(justech_approval_skip=True).action_confirm()
        inv = so._create_invoices()
        self.assertTrue(inv.invoice_line_ids.mapped("sale_line_ids"))
        action = inv.action_justech_invoice_link_existing_po()
        self.assertEqual(action.get("res_model"), "justech.link.existing.po.wizard")

    def test_18_customer_invoice_without_sol(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
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
        action = move.action_justech_invoice_link_existing_po()
        self.assertEqual(action.get("type"), "ir.actions.client")

    def test_19_po_and_bill_do_not_double(self):
        so = self._so(10)
        po = self._po(10)
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so.order_line[0], 10)
        bill = self._vendor_bill(10)
        aml = bill.invoice_line_ids[0]
        aml.purchase_line_id = pol.id
        # Ya cubierto: candidatos factura in_invoice con pending 0 no aparecen
        vals = self.env["justech.link.existing.po.wizard"]._prepare_candidate_bill_lines_for(
            so
        )
        self.assertFalse(any(v["vendor_bill_line_id"] == aml.id for v in vals))
        sol = self._refresh(so.order_line[0])
        self.assertAlmostEqual(sol.justech_qty_purchased, 10)

    def test_20_21_22_23_accounting_intact(self):
        so = self._so(5)
        bill = self._vendor_bill(5, price=200)
        aml = bill.invoice_line_ids[0]
        snap = {
            "debit": aml.debit,
            "credit": aml.credit,
            "balance": aml.balance,
            "amount_currency": aml.amount_currency,
            "residual": bill.amount_residual,
            "payment_state": bill.payment_state,
            "payments": self.env["account.payment"].search_count([]),
            "reconcile": self.env["account.partial.reconcile"].search_count([]),
        }
        self._link_bill_wiz(so, aml, qty=5).action_confirm_link()
        aml.invalidate_recordset()
        bill.invalidate_recordset()
        self.assertAlmostEqual(aml.debit, snap["debit"])
        self.assertAlmostEqual(aml.credit, snap["credit"])
        self.assertAlmostEqual(aml.balance, snap["balance"])
        self.assertAlmostEqual(aml.amount_currency, snap["amount_currency"])
        self.assertAlmostEqual(bill.amount_residual, snap["residual"])
        self.assertEqual(bill.payment_state, snap["payment_state"])
        self.assertEqual(self.env["account.payment"].search_count([]), snap["payments"])
        self.assertEqual(
            self.env["account.partial.reconcile"].search_count([]), snap["reconcile"]
        )

    def test_24_assignments_idempotent_cancel(self):
        so = self._so(4)
        bill = self._vendor_bill(4)
        aml = bill.invoice_line_ids[0]
        self._link_bill_wiz(so, aml, qty=4).action_confirm_link()
        assign = self.env["justech.purchase.sale.qty.assignment"].search(
            [("vendor_bill_line_id", "=", aml.id), ("state", "=", "active")]
        )
        self.assertEqual(len(assign), 1)
        assign.action_cancel()
        self.assertAlmostEqual(self._refresh(so.order_line[0]).justech_qty_purchased, 0)
        self.assertAlmostEqual(aml._justech_bill_qty_available(), 4)

    def test_button_label(self):
        so = self._so(2)
        action = so.action_justech_link_existing_po()
        self.assertEqual(action.get("name"), "Relacionar compra existente")
