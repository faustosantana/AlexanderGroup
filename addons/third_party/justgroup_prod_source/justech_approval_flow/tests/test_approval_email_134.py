# -*- coding: utf-8 -*-

from odoo.tests import tagged
from unittest.mock import patch

from lxml import etree

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApprovalEmail134(JustechApprovalCase):
    def _approval_mail(self, request):
        return (
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

    def _activity_assignment_messages(self, document):
        return self.env["mail.message"].sudo().search(
            [
                ("message_type", "=", "user_notification"),
                ("model", "=", document._name),
                ("res_id", "=", document.id),
                "|",
                ("subject", "ilike", "asignaron"),
                ("body", "ilike", "asignaron"),
            ]
        )

    def test_premium_mail_force_sent_sale(self):
        so = self._so().with_user(self.user_requester)
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        mail = self._approval_mail(request)
        self.assertTrue(mail)
        self.assertIn(mail.state, ("sent", "outgoing"))
        body = mail.body_html or mail.body or ""
        self.assertIn("APROBAR", body)
        self.assertIn("RECHAZAR", body)
        self.assertIn("VER EN ODOO", body)
        self.assertIn(self.user_approver.email, mail.email_to or "")

    def test_premium_mail_force_sent_purchase(self):
        po = self._po().with_user(self.user_requester)
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        request = po.justech_approval_request_id
        mail = self._approval_mail(request)
        self.assertTrue(mail)
        body = mail.body_html or mail.body or ""
        self.assertIn("APROBAR", body)
        self.assertIn("RECHAZAR", body)

    def test_premium_mail_force_sent_invoice(self):
        inv = self._invoice().with_user(self.user_requester)
        inv.action_justech_request_approval()
        request = inv.justech_approval_request_id
        mail = self._approval_mail(request)
        self.assertTrue(mail)
        body = mail.body_html or mail.body or ""
        self.assertIn("APROBAR", body)

    def test_activity_exists_without_assignment_email_sale(self):
        so = self._so().with_user(self.user_requester)
        so.action_justech_request_approval()
        act_type = self.env.ref("justech_approval_flow.mail_activity_approval")
        self.assertEqual(
            len(so.activity_ids.filtered(lambda a: a.activity_type_id == act_type)), 1
        )
        self.assertFalse(self._activity_assignment_messages(so))

    def test_no_redundant_request_button_sale_form(self):
        view = self.env.ref("justech_approval_flow.view_sale_order_form_justech_approval")
        arch = etree.fromstring(view.arch)
        buttons = arch.xpath(
            "//header//button[@name='action_justech_open_request_wizard']"
        )
        self.assertFalse(buttons)

    def test_no_redundant_request_button_purchase_form(self):
        view = self.env.ref(
            "justech_approval_flow.view_purchase_order_form_justech_approval"
        )
        arch = etree.fromstring(view.arch)
        buttons = arch.xpath(
            "//header//button[@name='action_justech_open_request_wizard']"
        )
        self.assertFalse(buttons)

    def test_no_redundant_request_button_invoice_form(self):
        view = self.env.ref(
            "justech_approval_flow.view_account_move_form_justech_approval"
        )
        arch = etree.fromstring(view.arch)
        buttons = arch.xpath(
            "//header//button[@name='action_justech_open_request_wizard']"
        )
        self.assertFalse(buttons)

    def test_sale_confirm_opens_wizard_not_direct_request(self):
        so = self._so().with_user(self.user_requester)
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertFalse(so.justech_approval_request_id)

    def test_purchase_confirm_opens_wizard(self):
        po = self._po().with_user(self.user_requester)
        action = po.with_context(justech_approval_force_wizard=True).button_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(po.state, "draft")

    def test_invoice_post_opens_wizard(self):
        inv = self._invoice().with_user(self.user_requester)
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(inv.justech_approval_state, "none")

    def test_mail_failure_still_records_error(self):
        so = self._so()
        template = self.env.ref("justech_approval_flow.mail_template_approval_request")
        with patch.object(type(template), "send_mail", side_effect=Exception("SMTP down")):
            so.action_justech_request_approval()
        request = so.justech_approval_request_id
        self.assertEqual(request.state, "pending")
        self.assertTrue(request.mail_error)

    def test_force_send_only_on_approval_templates(self):
        sent_flags = []
        Template = type(self.env["mail.template"])
        original_send = Template.send_mail

        def tracking_send(template_self, res_ids, force_send=False, **kwargs):
            sent_flags.append(
                {
                    "model": template_self.model_id.model,
                    "force_send": force_send,
                }
            )
            return original_send(
                template_self, res_ids, force_send=force_send, **kwargs
            )

        other = self.env["mail.template"].search(
            [("model", "=", "res.partner")], limit=1
        )
        self.assertTrue(other)
        with patch.object(Template, "send_mail", tracking_send):
            so = self._so().with_user(self.user_requester)
            so.action_justech_request_approval()
            other.send_mail(self.partner.id, force_send=False)
        af_flags = [f for f in sent_flags if f["model"] == "justech.approval.request"]
        other_flags = [f for f in sent_flags if f["model"] != "justech.approval.request"]
        self.assertTrue(af_flags)
        self.assertTrue(all(f["force_send"] for f in af_flags))
        self.assertTrue(other_flags)
        self.assertFalse(other_flags[0]["force_send"])

    def test_mail_brand_label_by_company(self):
        jo = self.env["res.company"].search([("name", "ilike", "Office")], limit=1)
        if jo:
            req = self.env["justech.approval.request"].new({"company_id": jo.id})
            self.assertEqual(req._mail_brand_label(), "JUST OFFICE")
        justech = self.env["res.company"].search([("name", "ilike", "JUSTECH")], limit=1)
        if justech:
            req = self.env["justech.approval.request"].new({"company_id": justech.id})
            self.assertEqual(req._mail_brand_label(), "JUSTECH")

    def test_normal_activity_still_notifies(self):
        from odoo.addons.mail.models.mail_activity import MailActivity as BaseMailActivity

        with patch.object(BaseMailActivity, "action_notify") as parent_notify:
            self.partner.activity_schedule(
                act_type_xmlid="mail.mail_activity_data_call",
                user_id=self.user_approver.id,
                summary="Llamada UAT normal",
            )
            parent_notify.assert_called()
        act_type = self.env.ref("justech_approval_flow.mail_activity_approval")
        so = self._so().with_user(self.user_requester)
        with patch.object(BaseMailActivity, "action_notify") as parent_notify:
            so.action_justech_request_approval()
            self.assertTrue(so.activity_ids.filtered(lambda a: a.activity_type_id == act_type))
            parent_notify.assert_not_called()
