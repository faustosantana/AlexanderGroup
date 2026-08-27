# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestTokenSecurity(JustechApprovalCase):
    def _raw_token_for(self, request):
        # regenerate to capture raw token for tests
        return request._generate_token()

    def test_valid_token_approve(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        self.assertFalse(request._token_error(raw))
        request.with_user(self.user_approver).action_approve(token_flow=True)
        self.assertEqual(request.state, "approved")
        self.assertTrue(request.token_used)
        self.assertTrue(request._token_error(raw))

    def test_invalid_and_tampered_token(self):
        Request = self.env["justech.approval.request"]
        self.assertTrue(Request._token_error("not-a-real-token"))
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        self.assertTrue(Request._token_error(raw + "x"))

    def test_used_token_rejected(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        request.with_user(self.user_approver).action_approve(token_flow=True)
        self.assertTrue(request._token_error(raw))

    def test_cancelled_document(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        so.with_user(self.user_requester).action_cancel()
        self.assertTrue(request._token_error(raw))

    def test_modified_document_invalidates_token(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        so.order_line[0].write({"price_unit": 333.0})
        request.invalidate_recordset()
        self.assertEqual(request.state, "invalidated")
        self.assertTrue(request._token_error(raw))

    def test_token_cannot_target_other_document(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        other = self._so(user=self.user_approver)
        rec = request._find_by_raw_token(raw)
        self.assertEqual(rec.res_id, so.id)
        self.assertNotEqual(rec.res_id, other.id)

    def test_expired_token(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        request.write({"token_expires_at": "2000-01-01 00:00:00"})
        self.assertTrue(request._token_error(raw))

    def test_replay_after_approve(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        request.with_user(self.user_approver).action_approve(token_flow=True)
        self.assertTrue(request._token_error(raw))
        with self.assertRaises(UserError):
            request.with_user(self.user_approver).action_approve(token_flow=True)

    def test_reject_after_approve_blocked(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        request.with_user(self.user_approver).action_approve(token_flow=True)
        with self.assertRaises(UserError):
            request.with_user(self.user_approver).action_reject(note="tarde", token_flow=True)

    def test_invalidate_then_token(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = self._raw_token_for(request)
        request.action_invalidate()
        self.assertTrue(request._token_error(raw))
