"""Hotfix: pagos reales vs reversed-por-NC; wizard 2 opciones; conversión."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_direct_cancel")
class TestReversedNotRealPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env["account.move"]
        cls.company = cls.env.company

    def _new_posted(self, **vals):
        defaults = {
            "move_type": "out_invoice",
            "company_id": self.company.id,
            "state": "posted",
            "payment_state": "not_paid",
            "justech_do_ncf": "B0100002999",
            "justech_do_ncf_voided": False,
            "justech_do_customer_delivery_state": "not_delivered",
            "is_move_sent": False,
            "amount_total": 100.0,
            "amount_residual": 100.0,
        }
        defaults.update(vals)
        return self.Move.new(defaults)

    def test_reversed_alone_is_not_real_payment(self):
        move = self._new_posted(payment_state="reversed", amount_residual=0.0)
        self.assertFalse(move._justech_has_real_payments())

    def test_gate_does_not_say_existen_pagos_for_reversed(self):
        # Without ids, CN conversion path can't run; ensure old message gone
        move = self._new_posted(payment_state="reversed", amount_residual=0.0)
        # NewId: no CNs → may fail other checks; must NOT be the old "existen pagos" for reversed
        err = move._justech_direct_cancel_gate_error()
        if err:
            self.assertNotIn("sin pagar", err.lower())
            self.assertNotIn("existen pagos o el estado", (err or "").lower())

    def test_wizard_only_two_actions(self):
        field = self.env["justech.do.invoice.correct.wizard"]._fields["action_choice"]
        keys = [k for k, _ in field.selection]
        self.assertEqual(keys, ["cancel_complete", "cancel_entry"])
        self.assertNotIn("correct_invoice", keys)
        self.assertNotIn("credit_partial", keys)

    def test_fiscal_treatment_only_608_and_607(self):
        field = self.env["justech.do.invoice.correct.wizard"]._fields[
            "fiscal_treatment_planned"
        ]
        keys = [k for k, _ in field.selection]
        self.assertEqual(set(keys), {"format_608", "rectify_607"})

    def test_case1_no_cn_allows(self):
        move = self._new_posted()
        self.assertFalse(move._justech_direct_cancel_gate_error())

    def test_paid_blocks_with_real_message(self):
        move = self._new_posted(payment_state="paid")
        err = move._justech_direct_cancel_gate_error()
        self.assertTrue(err)
        self.assertIn("pago", err.lower())
