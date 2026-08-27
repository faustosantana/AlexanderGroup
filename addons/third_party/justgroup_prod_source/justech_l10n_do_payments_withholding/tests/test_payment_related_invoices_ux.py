# -*- coding: utf-8 -*-
"""UX — Facturas relacionadas en pagos (display-only; sin publicar facturas fiscales)."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_payment_related_invoices_ux")
class TestPaymentRelatedInvoicesUX(TransactionCase):
    """Pruebas del detalle UX. No publican facturas (evitan gate RNC de BD operativa)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.journal:
            raise AssertionError("Se requiere diario bank/cash")
        cls.payment_method_line = cls.journal.inbound_payment_method_line_ids[:1]
        if not cls.payment_method_line:
            raise AssertionError("Se requiere payment_method_line inbound")
        cls.invoice = cls.env["account.move"].search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice", "out_refund", "in_refund")),
                ("state", "=", "posted"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
            order="id desc",
        )
        if not cls.invoice:
            raise AssertionError("Se requiere al menos una factura posted en la BD de prueba")
        cls.partner = cls.invoice.partner_id

    def _payment(self, amount=25.0):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound" if self.invoice.move_type.startswith("out") else "outbound",
                "partner_type": "customer" if self.invoice.move_type.startswith("out") else "supplier",
                "partner_id": self.partner.id,
                "amount": amount,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.journal.id,
                "payment_method_line_id": (
                    self.payment_method_line.id
                    if self.invoice.move_type.startswith("out")
                    else (self.journal.outbound_payment_method_line_ids[:1] or self.payment_method_line).id
                ),
                "date": date.today(),
                "memo": "UX related invoices",
            }
        )
        payment.action_post()
        return payment

    def _line(self, payment, move=None, applied=10.0, ncf=None, name=None, total=None):
        move = move or self.invoice
        return self.env["justech.payment.application.line"].create(
            {
                "payment_id": payment.id,
                "move_id": move.id,
                "invoice_name": name or move.name,
                "ncf": ncf or move.justech_do_ncf or move.l10n_latam_document_number or "B0100000001",
                "invoice_date": move.invoice_date,
                "invoice_total": total if total is not None else move.amount_total,
                "applied_amount": applied,
                "net_amount": applied,
                "reconciliation_state": "Pagada",
            }
        )

    def test_single_invoice_detail_fields(self):
        payment = self._payment()
        line = self._line(payment, applied=25.0)
        self.assertEqual(line.move_id, self.invoice)
        self.assertEqual(line.partner_id, self.partner)
        self.assertTrue(line.invoice_total)
        self.assertAlmostEqual(line.applied_amount, 25.0, places=2)
        self.assertEqual(line.amount_residual, self.invoice.amount_residual)
        self.assertEqual(
            line._fields["amount_residual"].string,
            "Balance pendiente",
        )
        self.assertIn(line.payment_state, dict(self.invoice._fields["payment_state"].selection))
        self.assertFalse(hasattr(type(line), "_compute_ncf_tooltip"))
        act = line.action_justech_open_invoice()
        self.assertEqual(act["res_model"], "account.move")
        self.assertEqual(act["res_id"], self.invoice.id)
        self.assertEqual(act["view_mode"], "form")

    def test_balance_pending_is_move_residual_not_total_minus_applied(self):
        """CASO A/C: Balance pendiente = residual contable vivo, no total − este pago."""
        payment = self._payment(30.0)
        # Snapshot display: total 50, aplicado 30 — residual real puede ser distinto
        # si ya había otros pagos/NC; la UX debe reflejar move.amount_residual.
        line = self._line(payment, applied=30.0, total=50.0)
        self.assertAlmostEqual(line.invoice_total, 50.0, places=2)
        self.assertAlmostEqual(line.applied_amount, 30.0, places=2)
        self.assertEqual(line.amount_residual, self.invoice.amount_residual)
        # No inventar 50-30 si el residual real no es 20
        naive = 50.0 - 30.0
        if abs(self.invoice.amount_residual - naive) > 0.0001:
            self.assertNotAlmostEqual(line.amount_residual, naive, places=2)
        self.assertEqual(line.amount_residual, line.move_id.amount_residual)

    def test_balance_pending_full_payment_zero_when_invoice_paid(self):
        """CASO B: si la factura está saldada, balance pendiente = 0."""
        paid = self.env["account.move"].search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice")),
                ("state", "=", "posted"),
                ("payment_state", "=", "paid"),
                ("company_id", "=", self.company.id),
                ("amount_residual", "=", 0),
            ],
            limit=1,
            order="id desc",
        )
        if not paid:
            self.skipTest("No hay factura pagada con residual 0 en BD de prueba")
        payment = self._payment(paid.amount_total or 50.0)
        line = self._line(payment, move=paid, applied=paid.amount_total or 50.0, total=paid.amount_total)
        self.assertAlmostEqual(line.amount_residual, 0.0, places=2)

    def test_ten_invoices_list(self):
        payment = self._payment(100.0)
        moves = self.env["account.move"].search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice")),
                ("state", "=", "posted"),
                ("company_id", "=", self.company.id),
            ],
            limit=10,
            order="id desc",
        )
        for i, move in enumerate(moves):
            self._line(payment, move=move, applied=10.0, name=f"{move.name}-ux{i}")
        while len(payment.justech_application_line_ids) < 10:
            n = len(payment.justech_application_line_ids)
            self._line(payment, applied=1.0, name=f"{self.invoice.name}-pad{n}", ncf=f"B02PAD{n:04d}")
        self.assertEqual(len(payment.justech_application_line_ids), 10)

    def test_fifty_display_lines_scroll_ready(self):
        payment = self._payment(500.0)
        self.env["justech.payment.application.line"].create(
            [
                {
                    "payment_id": payment.id,
                    "move_id": self.invoice.id,
                    "invoice_name": f"{self.invoice.name}-{i}",
                    "ncf": f"E310000{i:06d}",
                    "invoice_date": self.invoice.invoice_date,
                    "invoice_total": 10.0,
                    "applied_amount": 10.0,
                    "net_amount": 10.0,
                    "reconciliation_state": "Parcialmente pagada",
                }
                for i in range(50)
            ]
        )
        self.assertEqual(len(payment.justech_application_line_ids), 50)

    def test_open_partner_and_payment_actions(self):
        payment = self._payment()
        line = self._line(payment)
        pact = line.action_justech_open_partner()
        self.assertEqual(pact["res_model"], "res.partner")
        self.assertEqual(pact["res_id"], self.partner.id)
        pay_act = line.action_justech_open_payment()
        self.assertEqual(pay_act["res_model"], "account.payment")
        self.assertEqual(pay_act["res_id"], payment.id)

    def test_refresh_does_not_change_payment_amount(self):
        payment = self._payment(40.0)
        self._line(payment, applied=40.0)
        amount = payment.amount
        move_state = payment.move_id.state
        payment.action_justech_refresh_related_invoices()
        self.assertAlmostEqual(payment.amount, amount, places=2)
        self.assertEqual(payment.move_id.state, move_state)

    def test_ncf_simple_field_no_dgii_tooltip(self):
        payment = self._payment()
        line = self._line(payment, ncf="B0100001630", applied=5.0)
        self.assertEqual(line.ncf, "B0100001630")
        self.assertNotIn("ncf_tooltip", line._fields)
        # Estado fiscal existe en modelo pero no se usa en esta UX
        self.assertIn("justech_do_fiscal_ui_status", line._fields)

    def test_multicurrency_residual_uses_move_currency(self):
        payment = self._payment()
        line = self._line(payment)
        self.assertEqual(line.move_currency_id, self.invoice.currency_id)
        self.assertEqual(line.amount_residual, self.invoice.amount_residual)

    def test_detail_form_view_exists_without_fiscal_fields(self):
        view = self.env.ref(
            "justech_l10n_do_payments_withholding.view_justech_payment_application_line_form"
        )
        arch = view.arch_db or ""
        self.assertIn("Balance pendiente", arch)
        self.assertIn("NCF / e-CF", arch)
        self.assertNotIn("Estado fiscal", arch)
        self.assertNotIn("Detalle NCF", arch)
        self.assertNotIn("DGII", arch)
        self.assertNotIn("ncf_tooltip", arch)
        self.assertNotIn("justech_do_fiscal_ui_status", arch)
