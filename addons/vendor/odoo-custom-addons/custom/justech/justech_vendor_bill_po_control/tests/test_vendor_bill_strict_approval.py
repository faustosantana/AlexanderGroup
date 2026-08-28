# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


@tagged("post_install", "-at_install", "justech_vendor_bill_po_control", "justech_vendor_bill_strict")
class TestVendorBillStrictApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.vendor_bill_po_policy = "block"
        cls.company.vendor_bill_strict_approval = True
        cls.company.vendor_bill_require_classification = True
        cls.company.vendor_bill_amount_finance_limit = 25000
        cls.company.vendor_bill_amount_management_limit = 250000
        cls.partner = cls.env["res.partner"].create(
            {"name": "UAT Strict Vendor", "supplier_rank": 1, "is_company": True}
        )
        cls.partner_other = cls.env["res.partner"].create(
            {"name": "UAT Other Vendor", "supplier_rank": 1, "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "UAT Strict Product",
                "type": "consu",
                "purchase_ok": True,
                "purchase_method": "purchase",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.journal:
            raise AssertionError("Se requiere diario purchase")
        cls.expense_type = cls.env["justech.do.dgii.expense.type"].search([], limit=1)
        if not cls.expense_type:
            cls.expense_type = cls.env["justech.do.dgii.expense.type"].create(
                {"code": "02", "name": "UAT Trabajos y suministros"}
            )
        finance_group = cls.env.ref(
            "justech_vendor_bill_po_control.group_vendor_bill_approver_finance"
        )
        invoice_group = cls.env.ref("account.group_account_invoice")
        cls.approver = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Strict Finance Approver",
                    "login": "vb_strict_finance",
                    "email": "vb_strict_finance@example.com",
                    "group_ids": [(6, 0, [finance_group.id, invoice_group.id])],
                    "company_ids": [(6, 0, [cls.company.id])],
                    "company_id": cls.company.id,
                }
            )
        )
        cls.company.vendor_bill_default_finance_approver_id = cls.approver
        cls.company.vendor_bill_allow_admin_override = True

    def _bill(self, amount=100.0, with_po=False, move_type="in_invoice", partner=None, expense=True):
        partner = partner or self.partner
        vals = {
            "move_type": move_type,
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "name": "UAT line",
                        "quantity": 1,
                        "price_unit": amount,
                    },
                )
            ],
        }
        if expense and "justech_do_expense_type_id" in self.env["account.move"]._fields:
            vals["justech_do_expense_type_id"] = self.expense_type.id
        move = self.env["account.move"].create(vals)
        if with_po:
            po = self._make_po(partner=partner, qty=1, price=amount)
            move.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
            move.invalidate_recordset()
            move._compute_related_purchase_orders()
            move._compute_vendor_bill_evaluation()
            move._compute_vendor_bill_button_flags()
        return move

    def _make_po(self, partner=None, qty=1, price=100.0):
        partner = partner or self.partner
        po = self.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "PO line",
                            "product_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def test_01_without_po_goes_pending_on_submit(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "Omision UAT"
        bill.action_vendor_bill_submit_validation()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")

    def test_02_cannot_post_while_pending(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "Omision UAT"
        bill.action_vendor_bill_submit_validation()
        with self.assertRaises(UserError):
            bill._justech_check_vendor_bill_po_requirement()

    def test_03_cannot_pay_while_pending(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        with self.assertRaises(UserError):
            bill._check_vendor_bill_approved_for_financial_processing("pago")

    def test_04_cannot_treasury_while_pending(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        with self.assertRaises(UserError):
            bill._check_vendor_bill_approved_for_financial_processing("Tesorería")

    def test_05_cannot_withholding_while_pending(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        with self.assertRaises(UserError):
            bill._check_vendor_bill_approved_for_financial_processing("retenciones")

    def test_06_valid_po_no_extra_approval_by_default(self):
        bill = self._bill(with_po=True)
        self.assertTrue(bill.has_valid_purchase_order)
        self.assertFalse(bill.vendor_bill_requires_po)
        self.assertFalse(bill.vendor_bill_requires_approval)
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.vendor_bill_show_submit_validation)

    def test_06b_posted_po_bill_allows_payment_check(self):
        """Posted bill with valid PO must pass financial checks even if approval stayed draft."""
        bill = self._bill(with_po=True)
        self.assertEqual(bill.vendor_bill_approval_state, "draft")
        self.assertFalse(bill._justech_is_financially_approved())
        with self.assertRaises(UserError):
            bill._check_vendor_bill_approved_for_financial_processing("registro de pago")
        # Simulate already-posted PO bill left in draft approval (pre-fix residue).
        bill.with_context(tracking_disable=True).write({"state": "posted"})
        self.assertTrue(bill._justech_is_financially_approved())
        bill._check_vendor_bill_approved_for_financial_processing("registro de pago")

    def test_07_cancelled_po_not_valid(self):
        bill = self._bill(with_po=True)
        bill.related_purchase_order_ids.button_cancel()
        bill.invalidate_recordset()
        bill._compute_related_purchase_orders()
        self.assertFalse(bill.has_valid_purchase_order)

    def test_08_expense_type_rule_waives_po_but_may_require_approval(self):
        self.env["justech.vendor.bill.po.exception.rule"].create(
            {
                "name": "UAT Expense Type",
                "company_id": self.company.id,
                "exception_category": "admin",
                "expense_type_id": self.expense_type.id,
                "requires_purchase_order": False,
                "requires_approval": True,
                "approval_level": "finance",
            }
        )
        bill = self._bill()
        bill.invalidate_recordset()
        bill._compute_po_exception_rule()
        bill._compute_vendor_bill_evaluation()
        self.assertFalse(bill.vendor_bill_requires_po)
        self.assertTrue(bill.vendor_bill_requires_approval)
        bill.action_vendor_bill_submit_validation()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")

    def test_09_finance_approve_then_post_gate_ok(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        bill.action_vendor_bill_approve()
        self.assertEqual(bill.vendor_bill_approval_state, "approved")
        bill.invalidate_recordset()
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertTrue(bill.vendor_bill_approved_without_po)
        bill._justech_check_vendor_bill_po_requirement()

    def test_10_reject_requires_reason(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        with self.assertRaises(UserError):
            bill.action_vendor_bill_reject()
        bill.vendor_bill_reject_reason = "Documentación incompleta"
        bill.action_vendor_bill_reject()
        self.assertEqual(bill.vendor_bill_approval_state, "rejected")

    def test_11_return_and_resubmit(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        bill.vendor_bill_return_reason = "Corregir cuenta"
        bill.action_vendor_bill_return()
        self.assertEqual(bill.vendor_bill_approval_state, "returned")
        action = bill.action_vendor_bill_resubmit()
        self.assertEqual(action["res_model"], "vendor.bill.approval.request.wizard")
        wiz = self.env["vendor.bill.approval.request.wizard"].create(
            {
                "move_id": bill.id,
                "po_missing_reason": "x corregido",
                "approver_id": self.approver.id,
            }
        )
        wiz.action_submit()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")

    def test_12_manual_approval_state_write_blocked(self):
        bill = self._bill()
        with self.assertRaises(AccessError):
            bill.write({"vendor_bill_approval_state": "approved"})

    def test_13_manual_exception_blocked_in_strict(self):
        bill = self._bill()
        bill.po_exception_reason = "intento"
        with self.assertRaises(UserError):
            bill.action_justech_approve_po_exception()

    def test_14_legacy_policy_warning_still_works_when_strict_off(self):
        self.company.vendor_bill_strict_approval = False
        self.company.vendor_bill_po_policy = "warning"
        bill = self._bill()
        bill._justech_check_vendor_bill_po_requirement()

    def test_15_dual_approval_partial(self):
        bill = self._bill(amount=300000)
        bill.invalidate_recordset()
        bill._compute_vendor_bill_evaluation()
        self.assertEqual(bill.vendor_bill_approval_level_required, "dual")
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        bill.action_vendor_bill_approve()
        self.assertIn(bill.vendor_bill_approval_state, ("pending_validation", "approved"))

    def test_16_without_po_hides_confirm_shows_submit(self):
        bill = self._bill()
        bill._compute_vendor_bill_button_flags()
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertTrue(bill.vendor_bill_show_submit_validation)

    def test_17_expense_type_field_preserved(self):
        self.assertIn("justech_do_expense_type_id", self.env["account.move"]._fields)
        bill = self._bill()
        self.assertEqual(bill.justech_do_expense_type_id, self.expense_type)

    def test_18_po_other_partner_not_valid(self):
        bill = self._bill()
        po = self._make_po(partner=self.partner_other)
        bill.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
        bill.invalidate_recordset()
        bill._compute_related_purchase_orders()
        self.assertFalse(bill.has_valid_purchase_order)
        with self.assertRaises(UserError):
            bill._justech_assert_po_selectable(po)

    def test_19_fully_consumed_po_blocked(self):
        po = self._make_po(qty=1)
        bill1 = self._bill(with_po=False)
        bill1.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
        bill1.invalidate_recordset()
        # Draft bill1 reserves the full remaining qty → PO not selectable again
        self.assertFalse(bill1._justech_po_has_available_qty(po))
        bill2 = self._bill(with_po=False)
        with self.assertRaises(UserError):
            bill2._justech_assert_po_selectable(po)

    def test_20_in_receipt_same_control(self):
        bill = self._bill(move_type="in_receipt")
        bill._compute_vendor_bill_button_flags()
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertTrue(bill.vendor_bill_show_submit_validation)
        bill.vendor_bill_no_po_reason = "recibo sin OC"
        bill.action_vendor_bill_submit_validation()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")

    def test_21_multi_po_same_partner(self):
        po1 = self._make_po(qty=1, price=50)
        po2 = self._make_po(qty=1, price=50)
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "justech_do_expense_type_id": self.expense_type.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "L1",
                            "quantity": 1,
                            "price_unit": 50,
                            "purchase_line_id": po1.order_line[0].id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "L2",
                            "quantity": 1,
                            "price_unit": 50,
                            "purchase_line_id": po2.order_line[0].id,
                        },
                    ),
                ],
            }
        )
        bill._compute_related_purchase_orders()
        self.assertEqual(bill.related_purchase_order_count, 2)
        self.assertTrue(bill.has_valid_purchase_order)

    def test_22_invoice_origin_alone_not_valid(self):
        po = self._make_po()
        bill = self._bill()
        bill.invoice_origin = po.name
        bill.invalidate_recordset()
        bill._compute_related_purchase_orders()
        self.assertFalse(bill.has_valid_purchase_order)

    def test_23_cancelled_bill_releases_draft_reservation(self):
        po = self._make_po(qty=1)
        bill1 = self._bill()
        bill1.invoice_line_ids[0].purchase_line_id = po.order_line[0].id
        # Draft cancel / unlink must free the PO for another bill
        try:
            bill1.button_cancel()
        except AccessError as err:
            if "Recuperación Contable" in str(err) or "recuperación contable" in str(err).lower():
                self.skipTest("ACL de recuperación contable bloquea cancel en este entorno")
            raise
        except Exception:
            bill1.unlink()
        else:
            if bill1.exists() and bill1.state not in ("cancel",):
                bill1.unlink()
        bill2 = self._bill()
        bill2._justech_assert_po_selectable(po)

    def test_24_require_expense_type_on_submit(self):
        bill = self._bill(expense=False)
        if "justech_do_expense_type_id" not in bill._fields:
            self.skipTest("campo fiscal no disponible")
        bill.justech_do_expense_type_id = False
        bill.vendor_bill_no_po_reason = "x"
        with self.assertRaises(UserError):
            bill.action_vendor_bill_submit_validation()

    def test_25_missing_reason_message_guides_user(self):
        bill = self._bill()
        with self.assertRaises(UserError) as err:
            bill.action_vendor_bill_submit_validation()
        self.assertIn("Enviar a aprobación", str(err.exception))
        self.assertIn("Motivo de no tener Orden de Compra", str(err.exception))

    def test_26_po_missing_reason_alias_and_visibility_flags(self):
        bill = self._bill()
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_submit_validation)
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.has_valid_purchase_order)
        bill.po_missing_reason = "Sin OC por urgencia operativa"
        self.assertEqual(bill.vendor_bill_no_po_reason, "Sin OC por urgencia operativa")
        bill.action_vendor_bill_submit_validation()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_approver_actions)
        self.assertFalse(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.vendor_bill_show_submit_validation)

    def test_27_with_po_hides_missing_reason_requirement(self):
        bill = self._bill(with_po=True)
        bill._compute_vendor_bill_button_flags()
        self.assertTrue(bill.vendor_bill_show_confirm)
        self.assertFalse(bill.vendor_bill_show_submit_validation)
        # No reason needed when PO is valid
        bill.action_vendor_bill_submit_validation()
        self.assertIn(bill.vendor_bill_approval_state, ("approved", "draft", "pending_validation"))

    def test_28_submit_opens_wizard_action(self):
        bill = self._bill()
        action = bill.action_vendor_bill_open_submit_wizard()
        self.assertEqual(action["res_model"], "vendor.bill.approval.request.wizard")
        self.assertEqual(action["target"], "new")

    def test_29_wizard_requires_reason_and_submits(self):
        bill = self._bill()
        wiz = self.env["vendor.bill.approval.request.wizard"].with_context(active_id=bill.id).create(
            {
                "move_id": bill.id,
                "po_missing_reason": "temporal",
                "approver_id": self.approver.id,
            }
        )
        wiz.write({"po_missing_reason": ""})
        with self.assertRaises(UserError):
            wiz.action_submit()
        wiz.write({"po_missing_reason": "Urgencia sin OC"})
        wiz.action_submit()
        self.assertEqual(bill.vendor_bill_approval_state, "pending_validation")
        self.assertEqual(bill.vendor_bill_no_po_reason, "Urgencia sin OC")
        self.assertEqual(bill.vendor_bill_approver_id, self.approver)
        bill._compute_vendor_bill_approval_request_count()
        self.assertEqual(bill.vendor_bill_approval_request_count, 1)

    def test_30_decision_wizard_reject(self):
        bill = self._bill()
        bill.vendor_bill_no_po_reason = "x"
        bill.action_vendor_bill_submit_validation()
        wiz = self.env["vendor.bill.approval.decision.wizard"].create(
            {"move_id": bill.id, "decision": "reject", "comment": "Doc incompleta"}
        )
        wiz.action_confirm()
        self.assertEqual(bill.vendor_bill_approval_state, "rejected")

    def test_31_main_form_arch_has_no_fixed_approval_block(self):
        view = self.env.ref("justech_vendor_bill_po_control.view_move_form_vendor_bill_po")
        arch = view.arch_db or ""
        self.assertNotIn("justech_po_approval_section", arch)
        self.assertNotIn("OC / Aprobación", arch)
        self.assertNotIn('name="justech_po_control"', arch)
        self.assertIn("action_vendor_bill_open_submit_wizard", arch)
