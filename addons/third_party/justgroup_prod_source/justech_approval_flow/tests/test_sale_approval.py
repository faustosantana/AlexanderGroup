# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestSaleApproval(JustechApprovalCase):
    def test_request_email_approve_then_confirm(self):
        so = self._so()
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        so.action_justech_request_approval()
        self.assertEqual(so.justech_approval_state, "pending")
        request = so.justech_approval_request_id
        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "justech.approval.request"), ("res_id", "=", request.id)]
        )
        self.assertTrue(mail)
        request.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "approved")
        self.assertEqual(so.state, "sale")

    def test_reject_blocks_confirm(self):
        so = self._so()
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_reject(
            note="margen"
        )
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "rejected")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_unauthorized(self):
        so = self._so()
        so.action_justech_request_approval()
        with self.assertRaises(AccessError):
            so.justech_approval_request_id.with_user(self.user_outsider).action_approve()

    def test_modification_requires_reapproval(self):
        so = self._so()
        so.action_justech_request_approval()
        so.order_line[0].write({"price_unit": 250.0})
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "invalidated")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        self.assertEqual(so.state, "sale")
        self.assertEqual(so.justech_approval_state, "approved")

    def test_approver_fallback_uses_login_when_email_empty(self):
        self.env["justech.approval.user.rule"].search([]).unlink()
        self.company.write({"justech_approval_user_ids": [(5, 0, 0)]})
        self.user_approver.partner_id.write({"email": False})
        self.user_approver.write({"login": "approver.login@example.com", "email": False})
        self.env["justech.approval.user.rule"].create(
            {
                "user_id": self.user_approver.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": True,
                "approve_invoice": True,
            }
        )
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        self.assertTrue(request)
        self.assertIn("approver.login@example.com", request.email_to or "")

    def test_duplicate_request_and_activity_dedupe(self):
        so = self._so()
        so.action_justech_request_approval()
        so.action_justech_request_approval()
        self.assertEqual(
            self.env["justech.approval.request"].search_count(
                [("document_model", "=", "sale.order"), ("res_id", "=", so.id), ("state", "=", "pending")]
            ),
            1,
        )
        act_type = self.env.ref("justech_approval_flow.mail_activity_approval")
        self.assertEqual(
            so.activity_ids.filtered(lambda a: a.activity_type_id == act_type).__len__(),
            1,
        )

    def test_edit_and_send_without_approval(self):
        so = self._so()
        so.order_line[0].write({"price_unit": 110.0})
        so.invalidate_recordset()
        self.assertEqual(so.justech_approval_state, "none")
        self.assertEqual(so.state, "draft")
        so.write({"state": "sent"})
        self.assertEqual(so.state, "sent")
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_approve_auto_confirms_sale(self):
        so = self._so()
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        self.assertEqual(so.state, "sale")
        self.assertEqual(so.justech_approval_state, "approved")

    def test_note_does_not_invalidate(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        so.message_post(body="chatter noise")
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")

    def test_multi_approver_first_decision_wins(self):
        other = self.env["res.users"].create(
            {
                "name": "Second Approver",
                "login": "appr2_%s" % self.user_approver.id,
                "email": "approver2@example.com",
                "group_ids": [(6, 0, self.user_approver.group_ids.ids)],
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        self.env["justech.approval.user.rule"].create(
            {
                "user_id": other.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": True,
                "approve_invoice": True,
            }
        )
        self.company.write({"justech_approval_user_ids": [(6, 0, (self.user_approver | other).ids)]})
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        self.assertIn(self.user_approver, request.approver_ids)
        self.assertIn(other, request.approver_ids)
        request.with_user(other).action_approve()
        request.invalidate_recordset()
        self.assertEqual(request.state, "approved")
        so.invalidate_recordset()
        self.assertEqual(so.state, "sale")
        with self.assertRaises(UserError):
            request.with_user(self.user_approver).action_reject(note="tarde")
