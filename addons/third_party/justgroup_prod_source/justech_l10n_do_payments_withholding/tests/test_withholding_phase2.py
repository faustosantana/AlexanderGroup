# -*- coding: utf-8 -*-
"""Fase 2 — wizard de pagos integra únicamente ``_get_withholding_account``."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.justech_l10n_do_payments_withholding.models.withholding_account_validation import (
    assert_withholding_account_allowed,
)


@tagged("post_install", "-at_install", "justech_withholding_phase2")
class TestWithholdingPhase2(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Catalog = cls.env["justech.do.withholding.catalog"]
        cls.Config = cls.env["justech.do.withholding.company.config"]
        cls.company = cls.env.company
        cls.Catalog.with_context(justech_sync_uat_withholdings=True).sync_catalog_from_taxes(
            cls.company
        )
        cls.Catalog.ensure_company_configs()
        # Cliente: RET-ISR-2 (both/both). Proveedor UAT: UAT-RET-ISR-2 (supplier/purchase).
        cls.cat_isr_customer = cls.Catalog.search([("code", "=", "RET-ISR-2")], limit=1)
        cls.cat_isr_vendor = cls.Catalog.search([("code", "=", "UAT-RET-ISR-2")], limit=1)
        cls.cat_itbis = cls.Catalog.search([("code", "=", "UAT-RET-ITBIS-30")], limit=1)
        if not cls.cat_isr_customer:
            cls.cat_isr_customer = cls.cat_isr_vendor
        Account = cls.env["account.account"]
        cls.fiscal_account = Account.search(
            [
                ("account_type", "in", ("liability_current", "liability_non_current")),
                ("active", "=", True),
            ],
            limit=1,
        )
        if "company_ids" in Account._fields:
            acc = Account.search(
                [
                    ("account_type", "=", "liability_current"),
                    ("active", "=", True),
                    "|",
                    ("company_ids", "in", cls.company.id),
                    ("company_ids", "=", False),
                ],
                limit=1,
            )
            if acc:
                cls.fiscal_account = acc
        cls.fiscal_account_b = False
        if cls.fiscal_account:
            ok, _, _ = assert_withholding_account_allowed(
                cls.fiscal_account, cls.company, raise_exception=False
            )
            if not ok:
                cls.fiscal_account = False
        if cls.fiscal_account:
            other = Account.search(
                [
                    ("id", "!=", cls.fiscal_account.id),
                    ("account_type", "in", ("liability_current", "liability_non_current")),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if other:
                ok2, _, _ = assert_withholding_account_allowed(
                    other, cls.company, raise_exception=False
                )
                if ok2:
                    cls.fiscal_account_b = other

        for cat in (cls.cat_isr_customer | cls.cat_isr_vendor | cls.cat_itbis).filtered(lambda c: c):
            vals = {}
            if cat.pending_confirmation:
                vals["pending_confirmation"] = False
            if not cat.active:
                vals["active"] = True
            if not cat.rate:
                vals["rate"] = 2.0 if "ISR" in (cat.code or "") else 30.0
            if vals:
                cat.write(vals)
        if cls.cat_itbis and cls.cat_itbis.partner_scope != "both":
            cls.cat_itbis.write({"partner_scope": "both", "move_scope": "both"})

        cls.bank_journal = cls.company_data["default_journal_bank"]
        if (cls.bank_journal.code or "").upper() in ("RET01", "RET02"):
            cls.bank_journal = cls.env["account.journal"].search(
                [
                    ("type", "=", "bank"),
                    ("company_id", "=", cls.company.id),
                    ("code", "not in", ("RET01", "RET02")),
                ],
                limit=1,
            ) or cls.bank_journal

        ExpenseType = cls.env.get("justech.do.expense.type")
        cls.expense_type = ExpenseType.search([], limit=1) if ExpenseType is not None else False

    def _activate_config(self, catalog, account=None, company=None):
        company = company or self.company
        account = account or self.fiscal_account
        if not catalog or not account:
            self.skipTest("Missing catalog or fiscal account")
        cfg = self.Config.search(
            [("catalog_id", "=", catalog.id), ("company_id", "=", company.id)],
            limit=1,
        )
        self.assertTrue(cfg)
        cfg.write({"account_id": account.id, "active_config": False, "date_from": False, "date_to": False})
        cfg.action_activate()
        return cfg

    def _deactivate_config(self, catalog, company=None):
        company = company or self.company
        cfg = self.Config.search(
            [("catalog_id", "=", catalog.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if cfg:
            cfg.action_deactivate()
            cfg.write({"account_id": False})

    def _create_out_invoice(self, amount=1000.0, tax=None, currency=None, partner=None):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": (partner or self.partner_a).id,
                "invoice_date": fields.Date.today(),
                "currency_id": (currency or self.company.currency_id).id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "UAT WH line",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [(6, 0, tax.ids)] if tax else False,
                        },
                    )
                ],
            }
        )
        move.action_post()
        return move

    def _create_in_invoice(self, amount=1000.0, tax=None):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner_a.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "UAT WH vendor",
                        "quantity": 1,
                        "price_unit": amount,
                        "tax_ids": [(6, 0, tax.ids)] if tax else False,
                    },
                )
            ],
        }
        if self.expense_type and "justech_do_expense_type_id" in self.env["account.move"]._fields:
            vals["justech_do_expense_type_id"] = self.expense_type.id
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move

    def _pay_invoice(self, move, catalogs, amount=None, partner_type="customer"):
        for cat in catalogs:
            account = self.fiscal_account
            if cat == self.cat_itbis and self.fiscal_account_b:
                account = self.fiscal_account_b
            self._activate_config(cat, account=account)
        applied = amount if amount is not None else abs(move.amount_residual)
        method_lines = (
            self.bank_journal.inbound_payment_method_line_ids
            if partner_type == "customer"
            else self.bank_journal.outbound_payment_method_line_ids
        )
        Register = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=move.ids,
        )
        wiz = Register.create(
            {
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": method_lines[:1].id,
                "amount": applied,
                "payment_date": fields.Date.today(),
                "justech_withholding_catalog_ids": [(6, 0, catalogs.ids)],
            }
        )
        if applied < abs(move.amount_residual) - 0.01:
            wiz.write(
                {
                    "custom_user_amount": applied,
                    "custom_user_currency_id": move.currency_id.id,
                    "payment_difference_handling": "open",
                }
            )
        wiz._justech_rebuild_register_withholding_lines()
        return wiz._create_payments()

    def test_01_selectable_excludes_pending_inactive(self):
        cat = self.cat_isr_customer
        self._activate_config(cat)
        selectable = self.Catalog._search_payment_selectable(
            self.company, partner_type="customer", move_scope="sale"
        )
        self.assertIn(cat, selectable)
        self._deactivate_config(cat)
        selectable2 = self.Catalog._search_payment_selectable(
            self.company, partner_type="customer", move_scope="sale"
        )
        self.assertNotIn(cat, selectable2)

    def test_02_pending_confirmation_blocked(self):
        cat = self.cat_isr_customer
        if not cat:
            self.skipTest("no isr catalog")
        self._activate_config(cat)
        cat.write({"pending_confirmation": True})
        try:
            with self.assertRaises(UserError):
                cat._get_withholding_account(self.company)
            selectable = self.Catalog._search_payment_selectable(self.company)
            self.assertNotIn(cat, selectable)
        finally:
            cat.write({"pending_confirmation": False})
            self._deactivate_config(cat)

    def test_03_inactive_config_blocked(self):
        cfg = self._activate_config(self.cat_isr_customer)
        cfg.action_deactivate()
        with self.assertRaises(UserError):
            self.cat_isr_customer._get_withholding_account(self.company)

    def test_04_legacy_get_account_blocked_in_payment_context(self):
        with self.assertRaises(UserError):
            self.cat_isr_customer.with_context(
                justech_payment_withholding=True
            ).get_account_for_company(self.company)

    def test_05_resolve_for_payment_uses_company_config(self):
        self._activate_config(self.cat_isr_customer)
        move = self._create_out_invoice(1000.0)
        account, amount, info = self.cat_isr_customer.resolve_for_payment(
            self.company, move, "customer", applied_amount=1000.0
        )
        self.assertEqual(account, self.fiscal_account)
        self.assertAlmostEqual(amount, 20.0, places=2)
        self.assertEqual(info["account_id"], account.id)
        self.assertTrue(info["account_nature"])

    def test_10_customer_payment_isr(self):
        move = self._create_out_invoice(1000.0)
        payment = self._pay_invoice(move, self.cat_isr_customer)
        self.assertEqual(len(payment), 1)
        self.assertTrue(payment.justech_withholding_line_ids)
        wh = payment.justech_withholding_line_ids[:1]
        self.assertEqual(wh.account_id, self.fiscal_account)
        self.assertIn(self.fiscal_account, payment.move_id.line_ids.mapped("account_id"))
        self.assertNotIn((payment.journal_id.code or "").upper(), {"RET01", "RET02"})

    def test_11_vendor_payment_isr(self):
        if not self.cat_isr_vendor:
            self.skipTest("no vendor isr catalog")
        if not self.expense_type:
            self.skipTest("no expense type for vendor 606")
        move = self._create_in_invoice(1000.0)
        payment = self._pay_invoice(move, self.cat_isr_vendor, partner_type="supplier")
        self.assertTrue(payment.justech_withholding_line_ids)
        self.assertEqual(
            payment.justech_withholding_line_ids.account_id[:1], self.fiscal_account
        )

    def test_12_partial_payment(self):
        move = self._create_out_invoice(1000.0)
        payment = self._pay_invoice(move, self.cat_isr_customer, amount=400.0)
        self.assertAlmostEqual(payment.justech_withholding_line_ids.amount, 8.0, places=2)
        self.assertTrue(abs(move.amount_residual) > 0)

    def test_13_two_partial_payments(self):
        move = self._create_out_invoice(1000.0)
        p1 = self._pay_invoice(move, self.cat_isr_customer, amount=300.0)
        residual = abs(move.amount_residual)
        p2 = self._pay_invoice(move, self.cat_isr_customer, amount=min(300.0, residual))
        self.assertEqual(len(p1 | p2), 2)

    def test_14_three_partial_payments(self):
        move = self._create_out_invoice(900.0)
        payments = self.env["account.payment"]
        for amt in (200.0, 200.0, 200.0):
            residual = abs(move.amount_residual)
            if residual < 0.01:
                break
            payments |= self._pay_invoice(
                move, self.cat_isr_customer, amount=min(amt, residual)
            )
        self.assertGreaterEqual(len(payments), 3)

    def test_15_itbis_and_isr_together(self):
        if not self.cat_itbis:
            self.skipTest("no itbis")
        tax = self.company_data.get("default_tax_sale")
        move = self._create_out_invoice(1000.0, tax=tax)
        payment = self._pay_invoice(move, self.cat_isr_customer | self.cat_itbis)
        self.assertEqual(len(payment.justech_withholding_line_ids), 2)

    def test_16_invalid_account_blocks_payment(self):
        cfg = self.Config.search(
            [("catalog_id", "=", self.cat_isr_customer.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": False, "active_config": False})
        move = self._create_out_invoice(500.0)
        with self.assertRaises(UserError):
            self.cat_isr_customer.resolve_for_payment(
                self.company, move, "customer", applied_amount=500.0
            )
        Register = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        )
        wiz = Register.create(
            {
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.bank_journal.inbound_payment_method_line_ids[:1].id,
                "amount": abs(move.amount_residual),
                "justech_withholding_catalog_ids": [(6, 0, self.cat_isr_customer.ids)],
            }
        )
        with self.assertRaises(UserError):
            wiz._justech_rebuild_register_withholding_lines()

    def test_17_other_company_config_isolation(self):
        other = self.env["res.company"].search([("id", "!=", self.company.id)], limit=1)
        if not other:
            self.skipTest("single company")
        self._activate_config(self.cat_isr_customer)
        with self.assertRaises(UserError):
            self.cat_isr_customer._get_withholding_account(other)

    def test_18_multicurrency_invoice_payment(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd or usd == self.company.currency_id:
            self.skipTest("no distinct USD")
        if not usd.active:
            usd.active = True
        move = self._create_out_invoice(100.0, currency=usd)
        payment = self._pay_invoice(move, self.cat_isr_customer)
        self.assertEqual(payment.currency_id, usd)
        self.assertTrue(payment.justech_withholding_line_ids)

    def test_19_cancel_payment_with_withholding(self):
        from odoo.exceptions import AccessError

        move = self._create_out_invoice(500.0)
        payment = self._pay_invoice(move, self.cat_isr_customer)
        self.assertTrue(payment.justech_withholding_line_ids)
        # Anulación puede estar bloqueada por justech_accounting_recovery en DEV.
        try:
            if hasattr(payment, "action_cancel"):
                payment.action_cancel()
                self.assertIn(payment.state, ("cancel", "canceled", "cancelled", "draft"))
            elif hasattr(payment, "action_draft"):
                payment.action_draft()
                self.assertEqual(payment.state, "draft")
            else:
                self.skipTest("no cancel API")
        except AccessError:
            self.skipTest("cancel blocked by accounting recovery guard")

    def test_20_ret_journal_blocked_with_catalog(self):
        ret = self.env["account.journal"].search(
            [("code", "in", ("RET01", "RET02"))],
            limit=1,
        )
        if not ret:
            self.skipTest("no RET journal")
        self._activate_config(self.cat_isr_customer)
        move = self._create_out_invoice(200.0)
        Register = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        )
        method = ret.inbound_payment_method_line_ids[:1]
        if not method:
            # Diario RET sin método en la compañía de prueba: validar helper directo.
            wiz = Register.create(
                {
                    "journal_id": self.bank_journal.id,
                    "payment_method_line_id": self.bank_journal.inbound_payment_method_line_ids[:1].id,
                    "amount": abs(move.amount_residual),
                    "justech_withholding_catalog_ids": [(6, 0, self.cat_isr_customer.ids)],
                }
            )
            wiz.journal_id = ret
            with self.assertRaises(UserError):
                wiz._justech_assert_no_legacy_ret_journal()
            return
        wiz = Register.create(
            {
                "journal_id": ret.id,
                "payment_method_line_id": method.id,
                "amount": abs(move.amount_residual),
                "justech_withholding_catalog_ids": [(6, 0, self.cat_isr_customer.ids)],
            }
        )
        with self.assertRaises(UserError):
            wiz._justech_validate_withholdings_before_create()

    def test_21_partner_wizard_recompute_uses_service(self):
        self._activate_config(self.cat_isr_customer)
        move = self._create_out_invoice(1000.0)
        wiz = self.env["justech.payment.partner.wizard"].create(
            {
                "partner_type": "customer",
                "partner_id": move.partner_id.id,
                "currency_id": move.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.bank_journal.inbound_payment_method_line_ids[:1].id,
                "payment_date": fields.Date.today(),
            }
        )
        line = self.env["justech.payment.partner.wizard.line"].create(
            {
                "wizard_id": wiz.id,
                "move_id": move.id,
                "apply": True,
                "amount_to_pay": 1000.0,
                "withholding_catalog_ids": [(6, 0, self.cat_isr_customer.ids)],
            }
        )
        line._recompute_line_withholdings()
        self.assertEqual(line.withholding_detail_ids.account_id, self.fiscal_account)
        self.assertTrue(line.withholding_detail_ids.account_nature)
        self.assertEqual(line.withholding_detail_ids.config_state, "configured")
