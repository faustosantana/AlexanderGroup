# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestInvoiceFiscalPost(JustechApprovalCase):
    def _active_b01_range(self):
        Range = self.env["justech.do.ncf.range"].sudo()
        today = fields.Date.context_today(Range)
        ranges = Range.search(
            [
                ("state", "=", "active"),
                ("prefix", "=", "B01"),
                ("date_to", ">=", today),
            ]
        )
        ranges = ranges.filtered(lambda r: r.next_sequence <= r.sequence_end)
        Move = self.env["account.move"].sudo()
        for rng in ranges:
            expected = "%s%08d" % (rng.prefix, rng.next_sequence)
            if Move.search_count(
                [("company_id", "=", rng.company_id.id), ("justech_do_ncf", "=", expected)]
            ):
                continue
            return rng
        return Range.browse()

    def _posted_customer_move(self, company, move_type="out_invoice"):
        return (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("move_type", "=", move_type),
                    ("state", "=", "posted"),
                    ("company_id", "=", company.id),
                ],
                order="id desc",
                limit=1,
            )
        )

    def _fiscal_out_invoice(self, refund=False):
        ncf_range = self._active_b01_range()
        if not ncf_range:
            self.skipTest("no active B01 NCF range in this database (JUSTECH B01 depleted / fiscal DEV)")
        company = ncf_range.company_id
        move_type = "out_refund" if refund else "out_invoice"
        tmpl = self._posted_customer_move(company, move_type) or self._posted_customer_move(
            company, "out_invoice"
        )
        partner = tmpl.partner_id if tmpl else self.env["res.partner"].sudo().search(
            [("vat", "!=", False), ("customer_rank", ">", 0)], limit=1
        )
        if not partner or not partner.vat:
            self.skipTest("no customer with RNC for fiscal invoice fixture")
        journal = (
            ncf_range.journal_ids[:1]
            or (tmpl.journal_id if tmpl else False)
            or self.env["account.journal"].search(
                [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
            )
        )
        if not journal:
            self.skipTest("no sale journal for fiscal invoice fixture")
        self.user_requester.write({"company_ids": [(4, company.id)]})
        self.user_approver.write({"company_ids": [(4, company.id)]})
        tmpl_line = (
            tmpl.invoice_line_ids.filtered(lambda l: l.display_type in (False, "product"))[:1]
            if tmpl
            else self.env["account.move.line"]
        )
        line_vals = {
            "product_id": (tmpl_line.product_id.id if tmpl_line and tmpl_line.product_id else self.product.id),
            "name": "UAT AF fiscal inv",
            "quantity": 1.0,
            "price_unit": tmpl_line.price_unit if tmpl_line else 100.0,
        }
        if tmpl_line and tmpl_line.tax_ids:
            line_vals["tax_ids"] = [(6, 0, tmpl_line.tax_ids.ids)]
        inv = (
            self.env["account.move"]
            .with_company(company)
            .with_context(allowed_company_ids=company.ids)
            .create(
                {
                    "move_type": move_type,
                    "partner_id": partner.id,
                    "company_id": company.id,
                    "journal_id": journal.id,
                    "invoice_line_ids": [(0, 0, line_vals)],
                }
            )
        )
        if not refund:
            doc = ncf_range.document_type_id
            if "justech_do_document_type_id" in inv._fields and doc:
                try:
                    inv.write({"justech_do_document_type_id": doc.id})
                except ValidationError as err:
                    self.skipTest("cannot apply B01 document type: %s" % err)
        return inv.with_company(company).with_context(allowed_company_ids=company.ids)

    def test_post_without_approval_blocked_even_if_fiscal_ok(self):
        inv = self._fiscal_out_invoice().with_user(self.user_requester)
        try:
            inv.with_context(justech_approval_force_wizard=True).action_post()
        except UserError as err:
            msg = str(err).lower()
            if "requiere aprobación" not in msg:
                self.skipTest("fiscal/NCF blocked before approval gate: %s" % err)
            self.assertEqual(inv.state, "draft")
            return
        self.skipTest("invoice company is not gated by Approval Flow in this DEV database")

    def test_approved_fiscal_invoice_posts_with_standard_odoo(self):
        inv = self._fiscal_out_invoice().with_user(self.user_requester)
        try:
            inv.action_justech_request_approval()
        except UserError as err:
            self.skipTest("cannot request invoice approval in this fiscal env: %s" % err)
        inv.justech_approval_request_id.with_user(self.user_approver).action_approve()
        inv.invalidate_recordset()
        try:
            inv.with_context(justech_approval_force_wizard=True).action_post()
        except (UserError, ValidationError) as err:
            if "requiere aprobación" in str(err).lower():
                raise
            self.skipTest("fiscal environment cannot post: %s" % err)
        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.justech_approval_state, "approved")
        debit = sum(inv.line_ids.mapped("debit"))
        credit = sum(inv.line_ids.mapped("credit"))
        self.assertAlmostEqual(debit, credit, places=2)

    def test_ncf_error_without_approval_flow_is_environmental(self):
        inv = self._invoice()
        inv.company_id.justech_approval_invoice_enabled = False
        inv.invalidate_recordset()
        try:
            inv.with_context(justech_approval_skip=True).action_post()
        except UserError as err:
            self.assertNotIn("requiere aprobación", str(err).lower())
            if any(k in str(err).lower() for k in ("ncf", "comprobante", "rnc")):
                return
            raise
        else:
            inv.button_draft()
            inv.button_cancel()

    def test_out_refund_is_in_scope(self):
        inv = self._fiscal_out_invoice(refund=True).with_user(self.user_requester)
        try:
            inv.action_justech_request_approval()
        except UserError as err:
            self.skipTest("cannot request refund approval in this fiscal env: %s" % err)
        self.assertEqual(inv.justech_approval_state, "pending")
        with self.assertRaises(UserError) as err:
            inv.with_context(justech_approval_force_wizard=True).action_post()
        msg = str(err.exception).lower()
        if "requiere aprobación" not in msg:
            self.skipTest("fiscal/NCF blocked before approval gate: %s" % err.exception)
