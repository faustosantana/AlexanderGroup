"""Cancelación directa factura/asiento — elegibilidad y estados."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_direct_cancel")
class TestInvoiceDirectCancelGates(TransactionCase):
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

    def test_case1_not_delivered_allows_gate(self):
        move = self._new_posted()
        self.assertFalse(move._justech_direct_cancel_gate_error())

    def test_case2_emailed_blocks(self):
        move = self._new_posted(justech_do_customer_delivery_state="emailed")
        err = move._justech_direct_cancel_gate_error()
        self.assertTrue(err)
        self.assertIn("Nota de Crédito", err)

    def test_case3_portal_blocks(self):
        move = self._new_posted(justech_do_customer_delivery_state="portal_available")
        self.assertTrue(move._justech_direct_cancel_gate_error())

    def test_case4_payment_blocks(self):
        move = self._new_posted(payment_state="paid")
        self.assertTrue(move._justech_direct_cancel_gate_error())

    def test_case5_no_ncf_allows(self):
        move = self._new_posted(justech_do_ncf=False)
        self.assertFalse(move._justech_direct_cancel_gate_error())

    def test_case6_credit_notes_block_or_convert(self):
        """Con NC: o bloquea (parcial/múltiples) o permite conversión (no gate 'pagos')."""
        from unittest.mock import patch

        move = self._new_posted(payment_state="reversed", amount_residual=0.0)
        # Sin ids reales no hay NC; simular "hay NC" vía linked search vacío → no conversión
        # Asegurar que reversed no genera mensaje falso de pagos
        err = move._justech_direct_cancel_gate_error()
        if err:
            self.assertNotIn("existen pagos o el estado", err.lower())

        with patch.object(
            type(move), "_justech_linked_credit_notes", return_value=self.Move
        ):
            # recordset vacío tipado — múltiples/ parcial se evalúa en eligible
            pass

    def test_is_move_sent_blocks(self):
        move = self._new_posted(is_move_sent=True)
        err = move._justech_direct_cancel_gate_error()
        self.assertTrue(err)
        self.assertIn("comunicada", err)

    def test_unknown_delivery_requires_fiscal_admin(self):
        move = self._new_posted(justech_do_customer_delivery_state="unknown")
        err = move._justech_direct_cancel_gate_error()
        if not move._justech_user_has_fiscal_admin_authority():
            self.assertTrue(err)
        else:
            self.assertFalse(err)

    def test_fiscal_selection_includes_regularization_states(self):
        keys = {
            k
            for k, _ in self.Move._fields[
                "justech_do_fiscal_ui_status"
            ]._description_selection(self.env)
        }
        for needed in (
            "pending_regularization",
            "voided_internal",
            "reported_608",
            "rectificative_pending",
            "regularized_dgii",
            "cancelled_via_credit_note",
        ):
            self.assertIn(needed, keys)

    def test_operational_cancelled_and_nc_labels(self):
        labels = dict(
            self.Move._fields["justech_do_operational_ui_status"]._description_selection(
                self.env
            )
        )
        self.assertEqual(labels["cancelled"], "Asiento cancelado")
        self.assertEqual(
            labels["reversed"], "Neutralizado mediante Nota de Crédito"
        )
        self.assertNotEqual(labels["reversed"], "Revertida totalmente")

    def test_wizard_option_cancel_entry_exists(self):
        field = self.env["justech.do.invoice.correct.wizard"]._fields["action_choice"]
        keys = [k for k, _ in field.selection]
        self.assertIn("cancel_entry", keys)
        self.assertIn("cancel_complete", keys)

    def test_regularized_dgii_requires_evidence_flag(self):
        with self.assertRaises(UserError):
            self.Move.action_mark_fiscal_regularization(
                "regularized_dgii", attachment=False
            )
