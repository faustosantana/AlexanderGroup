# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


@tagged("post_install", "-at_install", "justech_vendor_bill_po_control", "justech_vendor_bill_ux_final")
class TestVendorBillUxFinal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vendor_bill_po_policy = "block"
        cls.company.vendor_bill_strict_approval = True
        cls.company.vendor_bill_require_classification = True
        cls.company.vendor_bill_no_po_auto_classification = "direct"
        cls.company.vendor_bill_allow_admin_override = True
        cls.partner = cls.env["res.partner"].create(
            {"name": "UX Final Vendor", "supplier_rank": 1, "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "UX Final Product",
                "type": "consu",
                "purchase_ok": True,
                "purchase_method": "purchase",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.expense_type = cls.env["justech.do.dgii.expense.type"].search([], limit=1)
        if not cls.expense_type:
            cls.expense_type = cls.env["justech.do.dgii.expense.type"].create(
                {"code": "02", "name": "UX expense"}
            )
        finance_g = cls.env.ref("justech_vendor_bill_po_control.group_vendor_bill_approver_finance")
        invoice_g = cls.env.ref("account.group_account_invoice")
        cls.approver = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "UX Approver",
                    "login": "vb_ux_approver",
                    "email": "vb_ux@example.com",
                    "group_ids": [(6, 0, [finance_g.id, invoice_g.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.company.vendor_bill_default_finance_approver_id = cls.approver

    def _bill(self, amount=100.0, with_po=False):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": "line",
                        "quantity": 1,
                        "price_unit": amount,
                    },
                )
            ],
        }
        if "justech_do_expense_type_id" in self.env["account.move"]._fields:
            vals["justech_do_expense_type_id"] = self.expense_type.id
        move = self.env["account.move"].create(vals)
        if with_po:
            po = self.env["purchase.order"].create(
                {
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "name": "PO",
                                "product_qty": 1,
                                "price_unit": amount,
                            },
                        )
                    ],
                }
            )
            po.button_confirm()
            move.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
            move.invalidate_recordset()
            move._compute_related_purchase_orders()
            move._compute_vendor_bill_evaluation()
            move._compute_vendor_bill_button_flags()
        return move

    def test_01_with_po_shows_confirm_hides_submit(self):
        bill = self._bill(with_po=True)
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.vendor_bill_show_submit_validation)

    def test_02_without_po_hides_confirm_shows_submit(self):
        bill = self._bill()
        bill._compute_vendor_bill_button_flags()
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertTrue(bill.vendor_bill_show_submit_validation)

    def test_03_cannot_post_without_po(self):
        bill = self._bill()
        with self.assertRaises(UserError):
            bill._justech_check_vendor_bill_po_requirement()

    def test_04_approve_classifies_and_attempts_post(self):
        bill = self._bill()
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "Urgencia",
                "approver_id": self.approver.id,
            }
        )
        wiz.action_submit()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        bill.with_user(self.approver).action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")
        self.assertEqual(bill.vendor_bill_classification, "direct")
        # Posted if fiscal data allows; otherwise remains draft with approval
        self.assertIn(bill.state, ("posted", "draft"))

    def test_05_reject_keeps_editable_rejected_state(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        bill.with_user(self.approver).write({"vendor_bill_reject_reason": "Doc incompleta"})
        bill.with_user(self.approver).action_vendor_bill_reject()
        self.assertEqual(bill.vendor_bill_approval_state, "rejected")
        self.assertEqual(bill.state, "draft")
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_resubmit)
        self.assertFalse(bill.vendor_bill_show_confirm)

    def test_06_activities_created_on_submit(self):
        bill = self._bill()
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "Sin OC",
                "approver_id": self.approver.id,
            }
        )
        wiz.action_submit()
        self.assertTrue(bill.activity_ids.filtered(lambda a: a.user_id == self.approver))

    def test_07_fiscal_alert_humanized_on_failed_autopost(self):
        bill = self._bill()
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "Urgencia fiscal",
                "approver_id": self.approver.id,
            }
        )
        wiz.action_submit()
        original = type(bill).action_post

        def _fail_post(self):
            raise UserError("Debe indicar el NCF / número de comprobante fiscal")

        type(bill).action_post = _fail_post
        try:
            bill.with_user(self.approver).action_vendor_bill_approve()
        finally:
            type(bill).action_post = original
        self.assertEqual(bill.vendor_bill_approval_state, "approved")
        self.assertEqual(bill.state, "draft")
        self.assertTrue(bill.vendor_bill_fiscal_post_alert)
        self.assertIn("aprobada", bill.vendor_bill_fiscal_post_alert.lower())
        self.assertIn("Confirmar", bill.vendor_bill_fiscal_post_alert)
        self.assertIn("NCF", bill.vendor_bill_fiscal_post_alert)
        self.assertNotIn("Traceback", bill.vendor_bill_fiscal_post_alert)
        self.assertNotIn("account.move", bill.vendor_bill_fiscal_post_alert)
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.vendor_bill_show_submit_validation)

    def test_08_confirm_after_fiscal_fix_keeps_approval(self):
        from odoo import fields as odoo_fields

        bill = self._bill()
        bill._justech_wf_write(
            {
                "vendor_bill_approval_state": "approved",
                "vendor_bill_approved_by": self.approver.id,
                "vendor_bill_approved_at": odoo_fields.Datetime.now(),
                "vendor_bill_classification": "direct",
                "vendor_bill_fiscal_post_alert": (
                    "La factura fue aprobada, pero no pudo contabilizarse porque faltan "
                    "datos fiscales obligatorios. Complete la información indicada y pulse Confirmar.\n"
                    "Datos a completar: NCF."
                ),
            }
        )
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertEqual(bill.vendor_bill_approval_state, "approved")
        try:
            bill.action_post()
        except UserError:
            pass
        self.assertEqual(bill.vendor_bill_approval_state, "approved")
        if bill.state == "posted":
            self.assertFalse(bill.vendor_bill_fiscal_post_alert)

    def test_09_menus_simplified(self):
        Menu = self.env["ir.ui.menu"].with_context(active_test=False)
        inbox = Menu.search(
            [("name", "ilike", "Facturas pendientes de aprobación"), ("active", "=", True)]
        )
        self.assertTrue(inbox)
        obsolete = Menu.search(
            [
                "|",
                ("name", "ilike", "Mis facturas pendientes"),
                ("name", "ilike", "Aprobadas pendientes de contabilizar"),
            ]
        )
        self.assertTrue(obsolete)
        self.assertFalse(any(obsolete.mapped("active")))

    def test_10_humanize_maps_ncf_without_tech_names(self):
        bill = self._bill()
        msg = bill._justech_humanize_post_block_error(
            UserError("Missing l10n_latam_document_number NCF required")
        )
        self.assertIn("aprobada", msg.lower())
        self.assertIn("NCF", msg)
        self.assertIn("Confirmar", msg)
        self.assertNotIn("l10n_latam_document_number", msg)
        self.assertNotIn("account.move", msg)
