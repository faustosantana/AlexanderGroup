# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.4 — pagos con monto <= 0 deben fallar; monto positivo pasa."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_l10n_do_payments_withholding.models.account_payment_amount import (
    JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG,
)


@tagged("post_install", "-at_install", "justech_hotfix_202614")
class TestPaymentAmountPositive(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.Payment = cls.env["account.payment"]
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "HOTFIX 2026.1.4 Test Partner",
                "company_id": cls.company.id,
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if not cls.journal:
            raise AssertionError("Se requiere un diario bank/cash para las pruebas de pago.")
        method = cls.journal.inbound_payment_method_line_ids[:1]
        if not method:
            method = cls.journal.outbound_payment_method_line_ids[:1]
        cls.payment_method_line = method
        if not cls.payment_method_line:
            raise AssertionError("Se requiere payment_method_line en el diario de prueba.")

    def _payment_vals(self, amount, payment_type="inbound"):
        partner_type = "customer" if payment_type == "inbound" else "supplier"
        method = self.payment_method_line
        if payment_type == "outbound":
            method = self.journal.outbound_payment_method_line_ids[:1] or method
        else:
            method = self.journal.inbound_payment_method_line_ids[:1] or method
        return {
            "payment_type": payment_type,
            "partner_type": partner_type,
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": self.company.currency_id.id,
            "journal_id": self.journal.id,
            "payment_method_line_id": method.id,
            "date": "2026-07-20",
            "memo": "HOTFIX 2026.1.4 test",
        }

    def test_create_amount_zero_fails(self):
        with self.assertRaises(UserError) as err:
            self.Payment.create(self._payment_vals(0.0))
        self.assertEqual(str(err.exception), JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def test_create_amount_negative_fails(self):
        with self.assertRaises(UserError) as err:
            self.Payment.create(self._payment_vals(-10.0))
        self.assertEqual(str(err.exception), JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def test_create_amount_positive_passes(self):
        payment = self.Payment.create(self._payment_vals(100.0))
        self.assertTrue(payment.id)
        self.assertEqual(payment.amount, 100.0)
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid", "posted"))

    def test_write_positive_to_zero_fails(self):
        payment = self.Payment.create(self._payment_vals(50.0))
        with self.assertRaises(UserError) as err:
            payment.write({"amount": 0.0})
        self.assertEqual(str(err.exception), JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def test_register_amount_zero_fails(self):
        Register = self.env["account.payment.register"]
        wiz = Register.new(
            {
                "amount": 0.0,
                "currency_id": self.company.currency_id.id,
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "payment_type": "inbound",
                "partner_id": self.partner.id,
            }
        )
        with self.assertRaises(UserError) as err:
            wiz._justech_assert_register_amount_positive()
        self.assertEqual(str(err.exception), JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def test_register_amount_negative_fails(self):
        Register = self.env["account.payment.register"]
        wiz = Register.new(
            {
                "amount": -5.0,
                "currency_id": self.company.currency_id.id,
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "payment_type": "inbound",
                "partner_id": self.partner.id,
            }
        )
        with self.assertRaises(UserError) as err:
            wiz._justech_assert_register_amount_positive()
        self.assertEqual(str(err.exception), JUSTECH_PAYMENT_AMOUNT_POSITIVE_MSG)

    def test_register_amount_positive_passes(self):
        Register = self.env["account.payment.register"]
        wiz = Register.new(
            {
                "amount": 25.0,
                "currency_id": self.company.currency_id.id,
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "payment_type": "inbound",
                "partner_id": self.partner.id,
            }
        )
        wiz._justech_assert_register_amount_positive()
