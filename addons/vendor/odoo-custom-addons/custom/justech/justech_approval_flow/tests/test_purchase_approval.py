# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestPurchaseApproval(JustechApprovalCase):
    def test_request_pending_email_and_approve(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        po.invalidate_recordset()
        self.assertEqual(po.state, "to approve")
        self.assertEqual(po.justech_approval_state, "pending")
        request = po.justech_approval_request_id
        self.assertEqual(request.state, "pending")
        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "justech.approval.request"), ("res_id", "=", request.id)]
        )
        self.assertTrue(mail)
        body = mail[0].body or mail[0].body_html or ""
        self.assertIn("APROBAR", body)
        self.assertIn("RECHAZAR", body)
        self.assertIn("VER EN ODOO", body)
        posted_before = self.env["account.move"].search_count([("state", "=", "posted")])
        aml_before = self.env["account.move.line"].search_count([])
        request.with_user(self.user_approver).action_approve()
        po.invalidate_recordset()
        self.assertEqual(po.state, "purchase")
        self.assertEqual(po.justech_approval_state, "approved")
        self.assertEqual(request.state, "approved")
        self.assertFalse(po.picking_ids)
        self.assertEqual(self.env["account.move"].search_count([("state", "=", "posted")]), posted_before)
        self.assertEqual(self.env["account.move.line"].search_count([]), aml_before)

    def test_duplicate_request_idempotent(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        first = po.justech_approval_request_id
        po.action_justech_request_approval()
        po.invalidate_recordset()
        second = po.justech_approval_request_id
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            self.env["justech.approval.request"].search_count(
                [("document_model", "=", "purchase.order"), ("res_id", "=", po.id), ("state", "=", "pending")]
            ),
            1,
        )

    def test_reject_returns_draft(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        request = po.justech_approval_request_id
        request.with_user(self.user_approver).action_reject(note="revisar precio")
        po.invalidate_recordset()
        self.assertEqual(po.state, "draft")
        self.assertEqual(po.justech_approval_state, "rejected")
        self.assertIn("revisar precio", request.decision_note)

    def test_unauthorized_cannot_approve(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        with self.assertRaises(AccessError):
            po.justech_approval_request_id.with_user(self.user_outsider).action_approve()

    def test_self_approve_blocked(self):
        self.user_requester.write({"group_ids": [(4, self.group_approver.id)]})
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        with self.assertRaises(AccessError):
            po.justech_approval_request_id.with_user(self.user_requester).action_approve()

    def test_self_approve_allowed_with_permission(self):
        self.user_requester.write(
            {"group_ids": [(4, self.group_approver.id), (4, self.group_self.id)]}
        )
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        po.justech_approval_request_id.with_user(self.user_requester).action_approve()
        po.invalidate_recordset()
        self.assertEqual(po.justech_approval_state, "approved")

    def test_pending_cannot_send_to_vendor(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        with self.assertRaises(UserError):
            po.action_rfq_send()

    def test_send_allowed_after_approve(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        po.justech_approval_request_id.with_user(self.user_approver).action_approve()
        po.invalidate_recordset()
        action = po.action_rfq_send()
        self.assertTrue(action)

    def test_pdf_final_blocked_until_approved(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        report = self.env.ref("purchase.action_report_purchase_order")
        with self.assertRaises(UserError) as err:
            report.report_action(po)
        self.assertIn("aún no ha sido aprobada", str(err.exception))
        with self.assertRaises(UserError):
            self.env["ir.actions.report"]._render_qweb_html(report.report_name, po.ids)
        po.justech_approval_request_id.with_user(self.user_approver).action_approve()
        po.invalidate_recordset()
        action = report.report_action(po)
        self.assertEqual(action.get("type"), "ir.actions.report")
        html = self.env["ir.actions.report"]._render_qweb_html(report.report_name, po.ids)[0]
        text = html.decode() if isinstance(html, bytes) else str(html)
        self.assertTrue(text)

    def test_rerequest_button_path_after_invalidate(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        req1 = po.justech_approval_request_id
        po.order_line[0].write({"price_unit": 77.0})
        req1.invalidate_recordset()
        po.invalidate_recordset()
        self.assertEqual(req1.state, "invalidated")
        self.assertEqual(po.justech_approval_state, "invalidated")
        action = po.action_justech_open_request_wizard()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertTrue(action.get("context", {}).get("justech_approval_rerequest"))
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval(
            note="re-request"
        )
        po.invalidate_recordset()
        req2 = self.env["justech.approval.request"].search(
            [
                ("document_model", "=", "purchase.order"),
                ("res_id", "=", po.id),
                ("state", "=", "pending"),
            ],
            limit=1,
        )
        self.assertTrue(req2)
        self.assertNotEqual(req1.id, req2.id)
        self.assertEqual(req1.state, "invalidated")


    def test_confirm_opens_approval_wizard_when_enabled(self):
        po = self._po().with_user(self.user_requester)
        action = po.with_context(justech_approval_force_wizard=True).button_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(po.state, "draft")

    def test_modification_invalidates_approval(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        request = po.justech_approval_request_id
        request.with_user(self.user_approver).action_approve()
        po.invalidate_recordset()
        self.assertEqual(po.state, "purchase")
        po2 = self._po().with_user(self.user_requester)
        po2.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        req2 = po2.justech_approval_request_id
        po2.order_line[0].write({"price_unit": 99.0})
        req2.invalidate_recordset()
        self.assertEqual(req2.state, "invalidated")
        self.assertEqual(po2.justech_approval_state, "invalidated")
        po2.invalidate_recordset()
        po2.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        po2.invalidate_recordset()
        req3 = po2.justech_approval_request_id.filtered(lambda r: r.state == "pending")
        self.assertTrue(req3)
        req3.with_user(self.user_approver).action_approve()
        po2.invalidate_recordset()
        self.assertEqual(po2.justech_approval_state, "approved")

    def test_notes_do_not_invalidate(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        request = po.justech_approval_request_id
        po.message_post(body="nota interna UAT")
        if "partner_ref" in po._fields:
            po.write({"partner_ref": "UAT-INTERNAL-REF"})
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")

    def test_chatter_author_is_requester(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        messages = po.sudo().message_ids.filtered(lambda m: "solicitó aprobación" in (m.body or ""))
        self.assertTrue(messages)
        self.assertEqual(messages[0].author_id, self.user_requester.partner_id)
