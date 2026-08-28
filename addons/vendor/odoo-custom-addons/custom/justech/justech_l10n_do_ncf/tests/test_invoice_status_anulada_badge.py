"""Dual UI status: payment badge stays accounting; fiscal badge shows NCF anulado.

Supersedes ambiguous «Anulada» override of status_in_payment (19.0.2.19.3 HOLD).
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_invoice_status")
class TestInvoiceDualStatusBadges(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env["account.move"]
        cls.company = cls.env.company

    def _new_move(self, **vals):
        defaults = {
            "move_type": "out_invoice",
            "company_id": self.company.id,
        }
        defaults.update(vals)
        return self.Move.new(defaults)

    def test_voided_keeps_payment_badge_posted(self):
        move = self._new_move(
            state="posted",
            payment_state="not_paid",
            justech_do_ncf_voided=True,
            justech_do_dgii_fiscal_state="cancelled",
            justech_do_ncf="B0100001591",
        )
        move._compute_status_in_payment()
        move._compute_justech_do_ui_statuses()
        self.assertEqual(move.status_in_payment, "posted")
        self.assertEqual(move.justech_do_fiscal_ui_status, "annulled")
        labels = dict(
            move._fields["justech_do_fiscal_ui_status"]._description_selection(self.env)
        )
        self.assertEqual(labels.get("annulled"), "Anulado")
        self.assertEqual(labels.get("voided_608"), "Anulado (608)")

    def test_voided_paid_keeps_paid_and_shows_ncf_anulado(self):
        move = self._new_move(
            state="posted",
            payment_state="paid",
            justech_do_ncf_voided=True,
            justech_do_ncf="B0100001591",
        )
        move._compute_status_in_payment()
        move._compute_justech_do_ui_statuses()
        self.assertEqual(move.status_in_payment, "paid")
        self.assertEqual(move.justech_do_fiscal_ui_status, "annulled")
        self.assertEqual(move.justech_do_operational_ui_status, "refund_pending")

    def test_reversed_shows_reversed_not_voided(self):
        move = self._new_move(
            state="posted",
            payment_state="reversed",
            justech_do_ncf_voided=False,
            justech_do_ncf="B0100001001",
        )
        move._compute_status_in_payment()
        move._compute_justech_do_ui_statuses()
        self.assertEqual(move.status_in_payment, "reversed")
        self.assertEqual(move.justech_do_fiscal_ui_status, "issued")
        self.assertEqual(move.justech_do_operational_ui_status, "reversed")

    def test_no_anulada_selection_on_status_in_payment(self):
        field = self.Move._fields["status_in_payment"]
        keys = [k for k, _v in field._description_selection(self.env)]
        self.assertNotIn("anulada", keys)
        self.assertIn("posted", keys)
        self.assertIn("paid", keys)
        self.assertIn("reversed", keys)

    def test_draft_and_cancel_operational(self):
        draft = self._new_move(state="draft", payment_state="not_paid")
        draft._compute_justech_do_ui_statuses()
        self.assertEqual(draft.justech_do_operational_ui_status, "draft")
        cancel = self._new_move(state="cancel", payment_state="not_paid")
        cancel._compute_justech_do_ui_statuses()
        self.assertEqual(cancel.justech_do_operational_ui_status, "cancelled")
