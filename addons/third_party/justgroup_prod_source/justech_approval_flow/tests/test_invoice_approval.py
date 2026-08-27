# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestInvoiceApproval(JustechApprovalCase):
    def test_draft_request_approve_then_post(self):
        inv = self._invoice().with_user(self.user_requester)
        self.assertEqual(inv.state, "draft")
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
        inv.action_justech_request_approval()
        self.assertEqual(inv.justech_approval_state, "pending")
        request = inv.justech_approval_request_id
        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "justech.approval.request"), ("res_id", "=", request.id)]
        )
        self.assertTrue(mail)
        request.with_user(self.user_approver).action_approve()
        inv.invalidate_recordset()
        self.assertEqual(inv.justech_approval_state, "approved")
        try:
            inv.with_context(justech_approval_force_wizard=True).action_post()
        except UserError as err:
            self.assertNotIn("requiere aprobación", str(err).lower())
        else:
            self.assertEqual(inv.state, "posted")
            debit = sum(inv.line_ids.mapped("debit"))
            credit = sum(inv.line_ids.mapped("credit"))
            self.assertAlmostEqual(debit, credit, places=2)

    def test_reject_blocks_post(self):
        inv = self._invoice().with_user(self.user_requester)
        inv.action_justech_request_approval()
        inv.justech_approval_request_id.with_user(self.user_approver).action_reject(
            note="revisar ITBIS"
        )
        inv.invalidate_recordset()
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")

    def test_vendor_bill_not_in_scope(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            bill.action_justech_request_approval()
        try:
            bill.with_context(justech_approval_force_wizard=True).action_post()
        except UserError as err:
            self.assertNotIn("requiere aprobación", str(err).lower())

    def test_in_refund_not_in_scope(self):
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1.0, "price_unit": 10.0})
                ],
            }
        )
        with self.assertRaises(UserError):
            refund.action_justech_request_approval()

    def test_modification_invalidates_draft_invoice(self):
        inv = self._invoice().with_user(self.user_requester)
        inv.action_justech_request_approval()
        inv.justech_approval_request_id.with_user(self.user_approver).action_approve()
        inv.invalidate_recordset()
        inv.invoice_line_ids[0].write({"price_unit": 999.0})
        inv.invalidate_recordset()
        self.assertEqual(inv.justech_approval_state, "invalidated")
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
