# -*- coding: utf-8 -*-
"""P0 JO-0000362: confirm without approval must fail when sale approval is on."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


MSG = "Esta cotización requiere aprobación antes de poder confirmarse."


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestSaleConfirmP0(JustechApprovalCase):
    def test_confirm_without_request_blocked(self):
        so = self._so()
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(so.state, "draft")
        self.assertEqual(so.justech_approval_state, "none")

    def test_confirm_sent_without_request_blocked(self):
        so = self._so()
        so.write({"state": "sent"})
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(so.state, "sent")

    def test_confirmation_error_message_hook(self):
        so = self._so().with_context(justech_approval_force_wizard=True)
        self.assertIn(MSG, so._confirmation_error_message() or "")

    def test_action_confirm_direct_blocked(self):
        so = self._so()
        with self.assertRaises(UserError) as err:
            so.with_context(justech_approval_force_wizard=True)._action_confirm()
        self.assertIn(MSG, str(err.exception))
        self.assertEqual(so.state, "draft")

    def test_pending_blocks_confirm(self):
        so = self._so()
        so.action_justech_request_approval()
        self.assertEqual(so.justech_approval_state, "pending")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_rejected_blocks_confirm(self):
        so = self._so()
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_reject(note="no")
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "rejected")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_invalidated_blocks_confirm(self):
        so = self._so()
        so.action_justech_request_approval()
        so.order_line[0].write({"product_uom_qty": 9.0})
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "invalidated")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_approved_auto_confirms(self):
        so = self._so()
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        self.assertEqual(so.state, "sale")
        self.assertEqual(so.justech_approval_state, "approved")

    def test_jo_style_flag_off_allows_confirm(self):
        """Root cause JO-0000362: Just Office had justech_approval_sale_enabled=False."""
        self.company.justech_approval_sale_enabled = False
        so = self._so()
        so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(so.state, "sale")

    def test_settings_sync_enables_other_company(self):
        other = self.env["res.company"].search([("id", "!=", self.company.id)], limit=1)
        if not other:
            self.skipTest("no second company in this database")
        other.write(
            {
                "justech_approval_sale_enabled": False,
                "justech_approval_purchase_enabled": False,
                "justech_approval_invoice_enabled": False,
            }
        )
        settings = self.env["res.config.settings"].create(
            {
                "company_id": self.company.id,
                "justech_approval_purchase_enabled": True,
                "justech_approval_sale_enabled": True,
                "justech_approval_invoice_enabled": True,
                "justech_approval_token_days": 14,
            }
        )
        settings.set_values()
        other.invalidate_recordset()
        self.assertTrue(other.justech_approval_sale_enabled)
