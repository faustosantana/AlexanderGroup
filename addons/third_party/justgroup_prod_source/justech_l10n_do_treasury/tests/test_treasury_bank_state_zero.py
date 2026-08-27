# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.4 — monto 0 nunca muestra Conciliado con el banco."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_hotfix_202614")
class TestTreasuryBankStateZero(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Payment = cls.env["account.payment"]

    def test_zero_amount_never_bank_reconciled(self):
        """Pagos históricos amount=0 no deben reportar bank_reconciled."""
        zeros = self.Payment.search([("amount", "=", 0), ("state", "in", ("paid", "in_process"))], limit=20)
        for pay in zeros:
            pay.invalidate_recordset(["treasury_bank_state"])
            self.assertNotEqual(
                pay.treasury_bank_state,
                "bank_reconciled",
                f"Pago {pay.id} amount=0 no puede ser Conciliado con el banco",
            )

    def test_positive_amount_compute_runs(self):
        pay = self.Payment.search(
            [("amount", ">", 0), ("state", "in", ("paid", "in_process"))],
            limit=1,
        )
        if not pay:
            self.skipTest("Sin pagos positivos publicados en la BD de prueba")
        pay.invalidate_recordset(["treasury_bank_state"])
        self.assertIn(pay.treasury_bank_state, ("bank_pending", "bank_reconciled", "not_posted"))
