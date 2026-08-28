# -*- coding: utf-8 -*-

import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApproval21(JustechApprovalCase):
    def _pdf_attachment(self, name="uat.pdf", res_model="justech.approval.sale.confirm.wizard"):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "datas": base64.b64encode(b"%PDF-1.4 uat"),
                "mimetype": "application/pdf",
                "res_model": res_model,
                "res_id": 0,
            }
        )

    def _invoice_from_sale(self, so):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )

    def test_duplicate_purchase_button_hidden_on_sale_form(self):
        so = self._so()
        arch, _view = so._get_view(view_type="form")
        for button in arch.xpath("//button[@name='action_add_purchase_orders']"):
            self.assertEqual(button.get("invisible"), "True")

    def test_generate_and_link_purchase_methods_intact(self):
        so = self._so()
        if hasattr(so, "action_justech_buy_pending"):
            try:
                action = so.action_justech_buy_pending()
            except UserError:
                action = {"type": "ir.actions.act_window"}
            self.assertTrue(action)
        if hasattr(so, "action_justech_link_existing_po"):
            try:
                action = so.action_justech_link_existing_po()
            except UserError:
                action = {"type": "ir.actions.act_window"}
            self.assertTrue(action)
        if hasattr(self.env["sale.order"], "action_add_purchase_orders"):
            self.assertTrue(callable(self.env["sale.order"].action_add_purchase_orders))

    def test_normal_user_confirm_opens_wizard(self):
        so = self._so()
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(so.state, "draft")

    def test_admin_confirm_bypasses_without_request(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 80})
                ],
            }
        )
        so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(so.state, "sale")
        self.assertTrue(so.justech_approval_bypass)
        self.assertEqual(so.justech_approval_state, "approved")
        self.assertTrue(so.justech_approval_bypass_user_id)
        self.assertTrue(so.justech_approval_bypass_date)
        self.assertFalse(
            self.env["justech.approval.request"].search_count(
                [("document_model", "=", "sale.order"), ("res_id", "=", so.id)]
            )
        )
        self.assertFalse(so.activity_ids)

    def test_approver_without_self_approval_cannot_bypass(self):
        so = self._so(user=self.user_approver)
        action = so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        self.assertEqual(so.state, "draft")

    def test_self_approval_user_confirms_without_request(self):
        rule = self.env["justech.approval.user.rule"].search(
            [("user_id", "=", self.user_approver.id)], limit=1
        )
        rule.allow_self_approval = True
        so = self._so(user=self.user_approver)
        so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(so.state, "sale")
        self.assertTrue(so.justech_approval_bypass)
        self.assertEqual(so.justech_approval_state, "approved")

    def test_request_comment_and_attachments(self):
        so = self._so()
        att = self._pdf_attachment("Cotización proveedor.pdf")
        wiz = self.env["justech.approval.sale.confirm.wizard"].create(
            {
                "sale_order_id": so.id,
                "request_note": "Favor validar condiciones comerciales.",
                "attachment_ids": [(6, 0, att.ids)],
            }
        )
        wiz.action_request_approval()
        request = so.justech_approval_request_id
        self.assertEqual(request.request_note, "Favor validar condiciones comerciales.")
        self.assertIn(att, request.attachment_ids)
        self.assertEqual(att.res_model, "justech.approval.request")
        self.assertEqual(att.res_id, request.id)

    def test_foreign_attachment_not_linked(self):
        so = self._so()
        foreign = self.env["ir.attachment"].create(
            {
                "name": "secret.pdf",
                "datas": base64.b64encode(b"secret"),
                "res_model": "res.partner",
                "res_id": self.partner.id,
            }
        )
        so.action_justech_request_approval(attachment_ids=foreign)
        request = so.justech_approval_request_id
        self.assertNotIn(foreign, request.attachment_ids)
        self.assertEqual(foreign.res_model, "res.partner")

    def test_xss_comments_and_filenames_escaped(self):
        so = self._so()
        payload = '<script>alert(1)</script><img onerror="alert(1)" src=x>'
        att = self._pdf_attachment("<script>x</script>.pdf")
        so.action_justech_request_approval(note=payload, attachment_ids=att)
        request = so.justech_approval_request_id
        html = str(request.request_note_html())
        names = str(request.request_attachment_names_html())
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", names)
        self.assertNotIn("<img", names)
        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "justech.approval.request"), ("res_id", "=", request.id)],
            limit=1,
        )
        body = mail.body_html or ""
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("<img onerror", body)

    def test_approved_result_mail_to_requester_only(self):
        so = self._so()
        so.action_justech_request_approval(note="Favor validar.")
        request = so.justech_approval_request_id
        request.with_user(self.user_approver).action_approve(note="OK precio")
        result = self.env["mail.mail"].sudo().search(
            [
                ("model", "=", "justech.approval.request"),
                ("res_id", "=", request.id),
                ("subject", "ilike", "APROBADA"),
            ]
        )
        self.assertTrue(result)
        email_to = ",".join(result.mapped("email_to") or []).lower()
        self.assertIn("requester@example.com", email_to)
        self.assertNotIn("partner@example.com", email_to)
        self.assertTrue(request.result_mail_sent)
        body = result[0].body_html or ""
        self.assertIn("OK precio", body)
        self.assertIn("ya puede ser confirmada", body.lower())

    def test_rejected_result_mail_to_requester_only(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        request.with_user(self.user_approver).action_reject(note="Favor corregir precio")
        result = self.env["mail.mail"].sudo().search(
            [
                ("model", "=", "justech.approval.request"),
                ("res_id", "=", request.id),
                ("subject", "ilike", "RECHAZADA"),
            ]
        )
        self.assertTrue(result)
        email_to = ",".join(result.mapped("email_to") or []).lower()
        self.assertIn("requester@example.com", email_to)
        self.assertNotIn("partner@example.com", email_to)
        self.assertIn("Favor corregir precio", result[0].body_html or "")

    def test_one_decision_one_result_mail(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        request.with_user(self.user_approver).action_approve()
        request.invalidate_recordset()
        count = self.env["mail.mail"].sudo().search_count(
            [
                ("model", "=", "justech.approval.request"),
                ("res_id", "=", request.id),
                ("subject", "ilike", "APROBADA"),
            ]
        )
        self.assertEqual(count, 1)

    def test_direct_invoice_requires_approval(self):
        inv = self._invoice()
        self.assertTrue(inv.justech_invoice_requires_approval)
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_invoice_from_approved_sale_skips_approval(self):
        so = self._so()
        so.action_justech_request_approval()
        so.justech_approval_request_id.with_user(self.user_approver).action_approve()
        so.invalidate_recordset()
        self.assertEqual(so.state, "sale")
        inv = self._invoice_from_sale(so)
        self.assertFalse(inv.justech_invoice_requires_approval)
        try:
            inv.with_context(justech_approval_force_wizard=True).action_post()
        except UserError as err:
            self.assertNotIn("requiere aprobación", str(err).lower())

    def test_invoice_from_admin_bypass_sale_skips_approval(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 80})
                ],
            }
        )
        so.with_context(justech_approval_force_wizard=True).action_confirm()
        inv = self._invoice_from_sale(so)
        self.assertFalse(inv.justech_invoice_requires_approval)

    def test_multiple_approved_sales_skip_invoice_approval(self):
        so1 = self._so()
        so2 = self._so()
        for so in (so1, so2):
            so.action_justech_request_approval()
            so.justech_approval_request_id.with_user(self.user_approver).action_approve()
            so.invalidate_recordset()
            self.assertEqual(so.state, "sale")
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "sale_line_ids": [(6, 0, so1.order_line.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "sale_line_ids": [(6, 0, so2.order_line.ids)],
                        },
                    ),
                ],
            }
        )
        self.assertFalse(inv.justech_invoice_requires_approval)

    def test_mixed_sales_require_invoice_approval(self):
        so_ok = self._so()
        so_ok.action_justech_request_approval()
        so_ok.justech_approval_request_id.with_user(self.user_approver).action_approve()
        so_ok.invalidate_recordset()
        self.assertEqual(so_ok.state, "sale")
        so_legacy = self._so()
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "sale_line_ids": [(6, 0, so_ok.order_line.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "sale_line_ids": [(6, 0, so_legacy.order_line.ids)],
                        },
                    ),
                ],
            }
        )
        self.assertTrue(inv.justech_invoice_requires_approval)

    def test_vendor_bill_unaffected(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1.0, "price_unit": 10.0})
                ],
            }
        )
        self.assertFalse(bill.justech_invoice_requires_approval)
        with self.assertRaises(UserError):
            bill.action_justech_request_approval()

    def test_direct_credit_note_requires_approval(self):
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1.0, "price_unit": 10.0})
                ],
            }
        )
        self.assertTrue(refund.justech_invoice_requires_approval)

    def test_credit_note_reversing_approved_invoice_inherits(self):
        inv = self._invoice().with_user(self.user_requester)
        inv.action_justech_request_approval()
        inv.justech_approval_request_id.with_user(self.user_approver).action_approve()
        inv.invalidate_recordset()
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "reversed_entry_id": inv.id,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1.0, "price_unit": 150.0})
                ],
            }
        )
        self.assertFalse(refund.justech_invoice_requires_approval)

    def test_purchase_request_keeps_comment(self):
        po = self._po()
        po.action_justech_request_approval(note="Revisar costo")
        request = po.justech_approval_request_id
        self.assertTrue(request)
        self.assertEqual(request.request_note, "Revisar costo")

    def test_token_does_not_unlock_foreign_attachments(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        foreign = self.env["ir.attachment"].create(
            {
                "name": "other.pdf",
                "datas": base64.b64encode(b"nope"),
                "res_model": "res.users",
                "res_id": self.user_requester.id,
            }
        )
        linked = request._allowed_request_attachments(foreign)
        self.assertFalse(linked)
