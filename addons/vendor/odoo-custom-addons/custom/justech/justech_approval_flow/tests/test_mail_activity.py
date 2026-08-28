# -*- coding: utf-8 -*-

from odoo.tests import tagged
from unittest.mock import patch

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestMailAndActivity(JustechApprovalCase):
    def test_activity_closed_on_approve(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        self.assertTrue(request.activity_id)
        request.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        act_type = self.env.ref("justech_approval_flow.mail_activity_approval")
        self.assertFalse(so.activity_ids.filtered(lambda a: a.activity_type_id == act_type))

    def test_mail_failure_keeps_pending_request(self):
        so = self._so()
        template = self.env.ref("justech_approval_flow.mail_template_approval_request")
        with patch.object(type(template), "send_mail", side_effect=Exception("SMTP down")):
            so.action_justech_request_approval()
        so.invalidate_recordset()
        request = so.justech_approval_request_id
        self.assertEqual(request.state, "pending")
        self.assertEqual(so.justech_approval_state, "pending")
        self.assertTrue(request.mail_error)

    def test_approval_mail_targets_approvers_not_customer(self):
        template = self.env.ref("justech_approval_flow.mail_template_approval_request")
        self.assertFalse(template.use_default_to)
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        mail = (
            self.env["mail.mail"]
            .sudo()
            .search(
                [
                    ("model", "=", "justech.approval.request"),
                    ("res_id", "=", request.id),
                ],
                order="id desc",
                limit=1,
            )
        )
        self.assertTrue(mail)
        envelope = ",".join(
            filter(
                None,
                [mail.email_to or ""] + (mail.recipient_ids.mapped("email") or []),
            )
        )
        self.assertIn(self.user_approver.email, envelope)
        self.assertNotIn(so.partner_id.id, mail.recipient_ids.ids)

    def test_snapshot_truncates_many_lines(self):
        so = self._so()
        extra = []
        for i in range(12):
            extra.append(
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_uom_qty": 1,
                        "price_unit": 10 + i,
                    },
                )
            )
        so.write({"order_line": extra})
        so.action_justech_request_approval()
        html = so.justech_approval_request_id.snapshot_html or ""
        self.assertIn("artículos adicionales", html)
