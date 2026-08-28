"""Blocker fixes: reverse&replace context, vendor CN wizard, e-CF Justech gate."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_invoice_cancel_flow")
class TestBlockerFixesCancelFlow(TransactionCase):
    def test_parse_action_context_string(self):
        Move = self.env["account.move"]
        parsed = Move._justech_parse_action_context({"context": "{'active_id': 7}"})
        self.assertEqual(parsed.get("active_id"), 7)
        self.assertEqual(Move._justech_parse_action_context({"context": {}}), {})
        self.assertEqual(Move._justech_parse_action_context({"context": ""}), {})
        self.assertEqual(
            Move._justech_parse_action_context({"context": "{'justech_reverse_and_replace': True}"}).get(
                "justech_reverse_and_replace"
            ),
            True,
        )

    def test_reverse_and_replace_builds_dict_context(self):
        """Replica la lógica de acción con context string estilo Odoo 19."""
        Move = self.env["account.move"]
        action = {
            "type": "ir.actions.act_window",
            "res_model": "account.move.reversal",
            "context": "{}",
        }
        ctx = Move._justech_parse_action_context(action)
        ctx["justech_reverse_and_replace"] = True
        ctx.setdefault("active_model", "account.move")
        ctx.setdefault("active_id", 99)
        ctx.setdefault("active_ids", [99])
        action["context"] = ctx
        self.assertIsInstance(action["context"], dict)
        self.assertTrue(action["context"]["justech_reverse_and_replace"])
        self.assertEqual(action["context"]["active_id"], 99)

    def test_ecf_gate_maps_accepted_state(self):
        move = self.env["account.move"].new(
            {
                "move_type": "out_invoice",
                "state": "posted",
                "justech_do_ncf": "E3100000999991",
                "company_id": self.env.company.id,
            }
        )
        # Simular estado aceptado vía mapping de send_state (Adel field si existe,
        # o monkeypatch seguro del método en la clase del recordset vacío).
        original = type(move)._justech_ecf_send_state

        def _fake_send_state(self):
            return "delivered_accepted"

        type(move)._justech_ecf_send_state = _fake_send_state
        try:
            err = move._justech_void_ncf_gate_error()
            self.assertTrue(err)
            self.assertIn("E34", err)
        finally:
            type(move)._justech_ecf_send_state = original

    def test_vendor_wizard_requires_ncf(self):
        purchase_j = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.env.company.id)], limit=1
        )
        partner = self.env["res.partner"].create({"name": "UAT Vendor CN"})
        move = self.env["account.move"].new(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": purchase_j.id,
                "state": "posted",
                "justech_do_purchase_registration_mode": "received",
                "company_id": self.env.company.id,
            }
        )
        wiz = self.env["account.move.reversal"].new({"company_id": self.env.company.id})
        wiz.move_ids = move
        wiz._compute_justech_vendor_cn()
        self.assertTrue(wiz.justech_needs_vendor_cn_data)
        with self.assertRaises(UserError):
            wiz._justech_validate_vendor_cn_data()
        wiz.justech_vendor_cn_ncf = "B0400099901"
        wiz.justech_vendor_cn_date = fields.Date.today()
        wiz._justech_validate_vendor_cn_data()
