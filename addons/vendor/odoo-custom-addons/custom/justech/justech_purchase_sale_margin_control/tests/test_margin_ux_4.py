# -*- coding: utf-8 -*-
"""19.0.4.0.0 — UX profesional, costos, backfill, bandeja, validación/aprobación."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginUX4(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "UX4 Co B"})
        cls.customer = cls.env["res.partner"].create({"name": "UX4 Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "UX4 Vendor"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "UX4 Batería",
                "type": "consu",
                "is_storable": True,
                "list_price": 200.0,
                "standard_price": 100.0,
            }
        )
        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.AddPO = cls.env["purchase.sale.add.purchase.wizard"]
        cls.Board = cls.env["purchase.sale.margin.board"]
        # Admin de prueba ya puede validar/aprobar (mismos supuestos que suite 2.0).

    def _so(self, qty=1.0, price=200.0):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": qty, "price_unit": price})
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, qty=1.0, price=100.0):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "price_unit": price})
                ],
            }
        )
        po.button_confirm()
        return po

    def _tx_sale(self, so):
        return self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": so.partner_id.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "name": so.name,
                "source": "manual",
                "state": "detected",
            }
        )

    def test_business_state_sale_without_cost(self):
        so = self._so()
        tx = self._tx_sale(so)
        self.assertEqual(tx.business_state, "need_relation")
        self.assertTrue(tx.pending_reason)
        self.assertEqual(tx.pending_actor, "purchases")
        self.assertIn("Agregar", tx.pending_action or "")

    def test_business_state_purchase_without_sale(self):
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, [po.id])],
                "supplier_ids": [(6, 0, [self.vendor.id])],
                "state": "detected",
            }
        )
        self.assertEqual(tx.business_state, "need_relation")
        self.assertEqual(tx.pending_action, "Relacionar con venta")

    def test_po_line_cost_not_zero(self):
        so = self._so()
        po = self._po(qty=2.0, price=185.0)
        tx = self._tx_sale(so)
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        wiz.action_refresh_lines()
        wiz.action_confirm()
        tx.invalidate_recordset()
        self.assertGreater(tx.cost_estimated_amount, 0.0)
        self.assertFalse(tx.invalid_cost_alert)
        line = tx.cost_line_ids.filtered("purchase_order_line_id")[:1]
        self.assertAlmostEqual(line.amount_untaxed, 370.0, places=2)

    def test_repair_zero_cost_line(self):
        so = self._so()
        po = self._po(price=50.0)
        tx = self._tx_sale(so)
        tx.write({"purchase_order_ids": [(4, po.id)]})
        line = tx.cost_line_ids.filtered(lambda l: l.purchase_order_line_id)[:1]
        line.write({"amount_untaxed": 0.0, "amount_tax": 0.0, "amount_total": 0.0})
        tx.invalidate_recordset()
        self.assertTrue(tx.invalid_cost_alert)
        tx.action_recompute_costs()
        line.invalidate_recordset()
        self.assertGreater(line.amount_untaxed, 0.0)

    def test_pending_action_banner_suggested(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "customer_id": so.partner_id.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "source": "backfill",
                "state": "detected",
            }
        )
        self.assertEqual(tx.business_state, "suggested")
        self.assertTrue(tx.pending_action_banner)
        self.assertIn("Compras", tx.pending_action_banner)

    def test_validate_wizard_flow(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "customer_id": so.partner_id.id,
                "state": "pending_review",
            }
        )
        wiz = self.env["purchase.sale.validate.wizard"].create({"transaction_id": tx.id})
        wiz.action_confirm()
        self.assertEqual(tx.state, "validated")
        self.assertEqual(tx.business_state, "finance_pending")

    def test_approve_wizard_flow(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "customer_id": so.partner_id.id,
                "state": "validated",
                "validation_state": "validated",
            }
        )
        wiz = self.env["purchase.sale.approve.wizard"].create({"transaction_id": tx.id})
        wiz.action_confirm()
        self.assertEqual(tx.state, "approved")
        self.assertEqual(tx.business_state, "approved")

    def test_relate_documents_wizard(self):
        so = self._so()
        po = self._po()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": "2026-03-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "purchase_line_id": po.order_line.id,
                        },
                    )
                ],
            }
        )
        # No action_post: reglas fiscales DEV bloquean partners sin NCF.
        wiz = self.env["purchase.sale.relate.documents.wizard"].create(
            {
                "company_id": self.company.id,
                "vendor_bill_id": bill.id,
                "sale_order_id": so.id,
                "amount_to_relate": 100.0,
            }
        )
        action = wiz.action_confirm()
        tx = self.Transaction.browse(action["res_id"])
        self.assertIn(so, tx.sale_order_ids)
        self.assertIn(bill, tx.vendor_bill_ids)

    def test_relate_documents_blocks_cross_company(self):
        so_other = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "company_id": self.other_company.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 20})
                ],
            }
        )
        with self.assertRaises(ValidationError):
            self.env["purchase.sale.relate.documents.wizard"].create(
                {
                    "company_id": self.company.id,
                    "sale_order_id": so_other.id,
                }
            ).action_confirm()

    def test_board_has_ux_kpis(self):
        so = self._so()
        self._tx_sale(so)
        board = self.Board.create({})
        board.action_refresh()
        self.assertTrue(hasattr(board, "related_costs_amount"))
        self.assertTrue(board.kpi_sales_no_cost_help)
        self.assertGreaterEqual(board.sales_without_cost_count, 1)

    def test_board_drill_down_sales_without_cost(self):
        so = self._so()
        self._tx_sale(so)
        board = self.Board.create({})
        action = board.action_open_sales_without_cost()
        self.assertEqual(action["res_model"], "purchase.sale.margin.transaction")

    def test_inbox_relate_opens_add_po_for_sale_without_cost(self):
        so = self._so()
        tx = self._tx_sale(so)
        action = tx.action_inbox_relate()
        self.assertEqual(action["res_model"], "purchase.sale.add.purchase.wizard")

    def test_chatter_natural_language_on_validate(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "pending_review",
            }
        )
        tx.action_validate_costs()
        messages = tx.message_ids.mapped("body")
        self.assertTrue(any("Compras validó" in (m or "") for m in messages))

    def test_chatter_natural_language_on_approve(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "validated",
                "validation_state": "validated",
            }
        )
        tx.action_approve()
        messages = tx.message_ids.mapped("body")
        self.assertTrue(any("Finanzas aprobó" in (m or "") for m in messages))

    def test_sync_creates_per_po_line_amounts(self):
        po = self._po(qty=3, price=40)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "detected",
            }
        )
        self.assertTrue(tx.cost_line_ids.filtered("purchase_order_line_id"))
        self.assertAlmostEqual(tx.cost_estimated_amount, 120.0, places=2)

    def test_display_amounts_prefer_estimated_when_no_real(self):
        so = self._so(price=500)
        po = self._po(price=200)
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertGreater(tx.display_sale_amount, 0)
        self.assertGreater(tx.display_cost_amount, 0)

    def test_payable_ux_labels(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": "2026-04-01",
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 80})
                ],
            }
        )
        aux = self.env["purchase.sale.payable.auxiliary"].create(
            {"company_id": self.company.id, "vendor_bill_id": bill.id}
        )
        self.assertEqual(aux.relation_status_label, "Sin venta relacionada")
        self.assertTrue(aux.what_is_missing)

    def test_backfill_dry_run_extended_counters(self):
        self._so()
        self._po()
        wiz = self.env["purchase.sale.backfill.wizard"].create(
            {"year": 2026, "dry_run": True, "batch_size": 0, "company_ids": [(6, 0, [self.company.id])]}
        )
        wiz.action_run()
        self.assertTrue(wiz.result_summary)
        self.assertIn("Simulación", wiz.result_summary)

    def test_backfill_apply_does_not_approve(self):
        so = self._so()
        wiz = self.env["purchase.sale.backfill.wizard"].create(
            {"year": 2026, "dry_run": False, "batch_size": 0, "company_ids": [(6, 0, [self.company.id])]}
        )
        wiz.action_run()
        txs = self.Transaction.search([("sale_order_ids", "in", so.id)])
        self.assertTrue(txs)
        self.assertTrue(all(t.state not in ("approved", "closed") for t in txs))

    def test_spanish_field_labels_on_transaction(self):
        field = self.Transaction._fields["business_state"]
        self.assertEqual(field.string, "Situación")
        self.assertEqual(self.Transaction._fields["pending_reason"].string, "¿Qué falta?")
        self.assertEqual(self.Transaction._fields["customer_id"].string, "Cliente")
        self.assertEqual(self.Transaction._fields["company_id"].string, "Empresa")

    def test_menu_actions_exist(self):
        self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_work_inbox")
        self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_unrelated_docs")
        self.env.ref("justech_purchase_sale_margin_control.action_purchase_sale_relate_documents_wizard")

    def test_exclude_from_inbox(self):
        so = self._so()
        tx = self._tx_sale(so)
        tx.action_inbox_exclude()
        self.assertFalse(tx.active)

    def test_finance_pending_shows_amounts_in_reason(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "validated",
                "validation_state": "validated",
            }
        )
        self.assertEqual(tx.business_state, "finance_pending")
        self.assertIn("aprobación", (tx.pending_reason or "").lower())

    def test_add_po_chatter_mentions_sale(self):
        so = self._so()
        po = self._po()
        tx = self._tx_sale(so)
        wiz = self.AddPO.create(
            {"company_id": self.company.id, "transaction_id": tx.id, "purchase_order_ids": [(6, 0, [po.id])]}
        )
        wiz.action_refresh_lines()
        wiz.action_confirm()
        bodies = " ".join(tx.message_ids.mapped("body") or []).lower()
        self.assertTrue("costo" in bodies or "compra" in bodies)

    def test_multi_po_costs_sum(self):
        so = self._so()
        po1 = self._po(price=30)
        po2 = self._po(price=70)
        tx = self._tx_sale(so)
        wiz = self.AddPO.create(
            {
                "company_id": self.company.id,
                "transaction_id": tx.id,
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
            }
        )
        wiz.action_refresh_lines()
        wiz.action_confirm()
        tx.invalidate_recordset()
        self.assertAlmostEqual(tx.cost_estimated_amount, 100.0, places=2)

    def test_primary_docs_computed(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
            }
        )
        self.assertEqual(tx.primary_sale_order_id, so)
        self.assertEqual(tx.primary_purchase_order_id, po)
        self.assertEqual(tx.primary_supplier_id, self.vendor)

    def test_validate_wizard_requires_confirmations(self):
        so = self._so()
        tx = self._tx_sale(so)
        tx.write({"state": "pending_review"})
        wiz = self.env["purchase.sale.validate.wizard"].create(
            {
                "transaction_id": tx.id,
                "confirm_supplier": False,
            }
        )
        with self.assertRaises(UserError):
            wiz.action_confirm()

    def test_rejected_business_state(self):
        so = self._so()
        tx = self._tx_sale(so)
        tx.action_reject()
        self.assertEqual(tx.business_state, "rejected")

    def test_closed_business_state(self):
        so = self._so()
        po = self._po()
        tx = self.Transaction.create(
            {
                "company_id": self.company.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "state": "approved",
                "validation_state": "validated",
                "approval_state": "approved",
            }
        )
        tx.action_close()
        self.assertEqual(tx.business_state, "closed")
        self.assertFalse(tx.pending_action_banner)
