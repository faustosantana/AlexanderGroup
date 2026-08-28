# -*- coding: utf-8 -*-
"""UAT: multi-invoice → single payment (register + manual wizard)."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install", "justech_payment")
class TestMultiInvoiceSinglePayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "UAT MultiPay Customer", "customer_rank": 1}
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "UAT MultiPay Other", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "UAT MultiPay Vendor", "supplier_rank": 1}
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.product = cls.env["product.product"].create(
            {"name": "UAT MultiPay Product", "list_price": 100.0, "type": "service"}
        )

    def _posted_invoice(self, partner, amount, move_type="out_invoice"):
        journal = self.sale_journal if move_type.startswith("out_") else self.purchase_journal
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "name": self.product.display_name,
                        },
                    )
                ],
            }
        )
        move.action_post()
        return move

    def test_register_group_payment_defaults_true(self):
        a = self._posted_invoice(self.partner, 100.0)
        b = self._posted_invoice(self.partner, 50.0)
        wiz = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[a.id, b.id])
            .create({})
        )
        self.assertTrue(wiz.can_group_payments)
        self.assertTrue(wiz.group_payment)

    def test_client_two_invoices_one_payment(self):
        a = self._posted_invoice(self.partner, 6928.30)
        b = self._posted_invoice(self.partner, 6891.20)
        before = self.env["account.payment"].search_count([])
        wiz = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[a.id, b.id])
            .create({"group_payment": True, "journal_id": self.journal.id})
        )
        payments = wiz._create_payments()
        self.assertEqual(len(payments), 1)
        self.assertEqual(self.env["account.payment"].search_count([]) , before + 1)
        self.assertAlmostEqual(payments.amount, 13819.50, places=2)
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual(
            float_compare(a.amount_residual, 0.0, precision_digits=2), 0
        )
        self.assertEqual(
            float_compare(b.amount_residual, 0.0, precision_digits=2), 0
        )

    def test_different_partner_no_silent_group(self):
        a = self._posted_invoice(self.partner, 100.0)
        b = self._posted_invoice(self.partner_b, 100.0)
        wiz = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[a.id, b.id])
            .create({})
        )
        # Core batches by partner → can_edit_wizard may be False → multiple payments
        payments = wiz._create_payments()
        self.assertGreaterEqual(len(payments), 2)

    def test_manual_wizard_partial(self):
        a = self._posted_invoice(self.partner, 6000.0)
        b = self._posted_invoice(self.partner, 10000.0)
        manual = self.env["multi.invoice.manual.payment.wizard"].create(
            {
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "payment_date": fields.Date.today(),
                "amount_received": 10000.0,
            }
        )
        manual._onchange_journal_id()
        manual._load_open_moves()
        lines = {l.move_id.id: l for l in manual.line_ids}
        lines[a.id].amount_to_apply = 6000.0
        lines[b.id].amount_to_apply = 4000.0
        action = manual.action_create_payment()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(payment.amount, 10000.0, places=2)
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual(
            float_compare(a.amount_residual, 0.0, precision_digits=2), 0
        )
        self.assertEqual(
            float_compare(b.amount_residual, 6000.0, precision_digits=2), 0
        )

    def test_supplier_three_bills_one_payment(self):
        bills = [
            self._posted_invoice(self.vendor, 1000.0, "in_invoice"),
            self._posted_invoice(self.vendor, 2000.0, "in_invoice"),
            self._posted_invoice(self.vendor, 500.0, "in_invoice"),
        ]
        before = self.env["account.payment"].search_count([])
        wiz = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[b.id for b in bills])
            .create({"group_payment": True, "journal_id": self.journal.id})
        )
        payments = wiz._create_payments()
        self.assertEqual(len(payments), 1)
        self.assertEqual(self.env["account.payment"].search_count([]), before + 1)
        self.assertEqual(payments.payment_type, "outbound")
        self.assertAlmostEqual(payments.amount, 3500.0, places=2)

    def test_menu_active(self):
        menu = self.env.ref(
            "multi_invoice_manual_payment_prod.menu_multi_invoice_manual_payment_root"
        )
        self.assertTrue(menu.active)
