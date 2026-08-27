"""Option C: Anular NCF ≠ Revertir factura — gates, wizard and chatter."""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_invoice_cancel_flow")
class TestInvoiceCancelReverseFlow(TransactionCase):
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
            "justech_do_ncf": "B0100099901",
            "justech_do_ncf_voided": False,
        }
        defaults.update(vals)
        return self.Move.new(defaults)

    def test_void_gate_blocks_ecf_accepted(self):
        move = self._new_posted(justech_do_ncf="E3100000000001")
        if "l10n_do_ecf_send_state" in move._fields:
            move.l10n_do_ecf_send_state = "delivered_accepted"
            err = move._justech_void_ncf_gate_error()
            self.assertTrue(err)
            self.assertIn("E34", err)

    def test_can_void_false_when_already_voided(self):
        move = self._new_posted(justech_do_ncf_voided=True)
        move._compute_justech_do_can_void_ncf()
        self.assertFalse(move.justech_do_can_void_ncf)

    def test_double_void_raises(self):
        move = self.Move.create(
            {
                "move_type": "entry",
                "date": fields.Date.context_today(self.Move),
                "journal_id": self.env["account.journal"]
                .search([("type", "=", "general")], limit=1)
                .id,
            }
        )
        # Lightweight: call method path with new() mock fields via browse after write
        inv = self._new_posted(justech_do_ncf_voided=True)
        with self.assertRaises(UserError):
            # ensure_one path via wizard open
            inv.action_open_void_ncf_wizard()

    def test_correct_wizard_recommends_reverse_when_voided_with_residual(self):
        move = self.Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "state": "posted",
                "payment_state": "not_paid",
                "amount_residual": 100.0,
                "amount_total": 100.0,
                "justech_do_ncf": "B0100001591",
                "justech_do_ncf_voided": True,
            }
        )
        wiz = self.env["justech.do.invoice.correct.wizard"].new({"move_id": move.id})
        # NewId: bind move manually
        wiz.move_id = move
        wiz._compute_context_fields()
        self.assertEqual(wiz.recommended_action, "cancel_complete")

    def test_void_wizard_requires_ack(self):
        move = self._new_posted()
        wiz = self.env["justech.do.ncf.void.wizard"].new(
            {
                "move_id": move.id,
                "cancel_type": "04",
                "acknowledge_accounting_intact": False,
            }
        )
        wiz.move_id = move
        with self.assertRaises(UserError):
            wiz.action_confirm_void()

    def test_selection_labels_ncf_anulado(self):
        field = self.Move._fields["justech_do_fiscal_ui_status"]
        labels = dict(field._description_selection(self.env))
        self.assertEqual(labels["voided_608"], "Anulado (608)")
        self.assertNotIn("Anulada", labels.values())
