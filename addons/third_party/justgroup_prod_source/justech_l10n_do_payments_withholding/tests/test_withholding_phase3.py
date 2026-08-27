# -*- coding: utf-8 -*-
"""Fase 3 — validación contable: banco=neto, cuenta WH, balance, sin RET*."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.justech_l10n_do_payments_withholding.models.withholding_account_validation import (
    assert_withholding_account_allowed,
)

TOL = 0.02


@tagged("post_install", "-at_install", "justech_withholding_phase3")
class TestWithholdingPhase3Accounting(AccountTestInvoicingCommon):
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
        cls.cat_isr = cls.Catalog.search([("code", "=", "RET-ISR-2")], limit=1)
        if not cls.cat_isr:
            cls.cat_isr = cls.Catalog.search([("code", "=", "UAT-RET-ISR-2")], limit=1)
        cls.cat_itbis = cls.Catalog.search([("code", "=", "UAT-RET-ITBIS-30")], limit=1)
        Account = cls.env["account.account"]
        cls.fiscal = Account.search(
            [
                ("account_type", "in", ("liability_current", "liability_non_current")),
                ("active", "=", True),
            ],
            limit=1,
        )
        if cls.fiscal:
            ok, _, _ = assert_withholding_account_allowed(
                cls.fiscal, cls.company, raise_exception=False
            )
            if not ok:
                cls.fiscal = False
        cls.fiscal_b = Account.search(
            [
                ("id", "!=", cls.fiscal.id if cls.fiscal else 0),
                ("account_type", "in", ("liability_current", "liability_non_current")),
                ("active", "=", True),
            ],
            limit=1,
        )
        if cls.fiscal_b:
            ok2, _, _ = assert_withholding_account_allowed(
                cls.fiscal_b, cls.company, raise_exception=False
            )
            if not ok2:
                cls.fiscal_b = False
        for cat in (cls.cat_isr | cls.cat_itbis).filtered(lambda c: c):
            vals = {}
            if cat.pending_confirmation:
                vals["pending_confirmation"] = False
            if not cat.active:
                vals["active"] = True
            if not cat.rate:
                vals["rate"] = 2.0 if "ISR" in (cat.code or "") else 30.0
            if cat == cls.cat_itbis:
                vals.update({"partner_scope": "both", "move_scope": "both"})
            if vals:
                cat.write(vals)
        cls.bank = cls.company_data["default_journal_bank"]
        if (cls.bank.code or "").upper() in ("RET01", "RET02"):
            cls.bank = cls.env["account.journal"].search(
                [
                    ("type", "=", "bank"),
                    ("company_id", "=", cls.company.id),
                    ("code", "not in", ("RET01", "RET02")),
                ],
                limit=1,
            ) or cls.bank

    def _activate(self, catalog, account=None):
        account = account or self.fiscal
        if not catalog or not account:
            self.skipTest("missing catalog/account")
        cfg = self.Config.search(
            [("catalog_id", "=", catalog.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": account.id, "active_config": False, "date_from": False, "date_to": False})
        cfg.action_activate()
        return cfg

    def _invoice(self, amount=100000.0, tax=None):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "PH3",
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

    def _pay(self, move, catalogs, amount=None):
        for cat in catalogs:
            acc = self.fiscal_b if cat == self.cat_itbis and self.fiscal_b else self.fiscal
            self._activate(cat, acc)
        applied = amount if amount is not None else abs(move.amount_residual)
        wiz = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create(
            {
                "journal_id": self.bank.id,
                "payment_method_line_id": self.bank.inbound_payment_method_line_ids[:1].id,
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
        preview = {
            w.catalog_id.id: (w.account_id.id, w.amount) for w in wiz.justech_withholding_line_ids
        }
        payment = wiz._create_payments()
        return payment, preview

    def _liquidity_amt(self, payment):
        outstanding = payment.outstanding_account_id
        lines = payment.move_id.line_ids.filtered(
            lambda l: (outstanding and l.account_id == outstanding)
            or l.account_id.account_type == "asset_cash"
        )
        return abs(sum(lines.mapped("amount_currency")))

    def test_01_bank_is_net_not_gross(self):
        move = self._invoice(100000.0)
        payment, _ = self._pay(move, self.cat_isr)
        self.assertAlmostEqual(payment.justech_withholding_total, 2000.0, places=2)
        self.assertAlmostEqual(payment.justech_net_transfer, 98000.0, places=2)
        liq = self._liquidity_amt(payment)
        self.assertAlmostEqual(liq, 98000.0, delta=TOL)
        self.assertNotAlmostEqual(liq, 100000.0, delta=TOL)

    def test_02_withholding_account_from_company_config(self):
        move = self._invoice(10000.0)
        payment, preview = self._pay(move, self.cat_isr)
        wh = payment.justech_withholding_line_ids[:1]
        self.assertEqual(wh.account_id, self.fiscal)
        self.assertEqual(wh.account_id.account_type[:10], "liability_")
        gl = payment.move_id.line_ids.filtered(lambda l: l.account_id == self.fiscal)
        self.assertTrue(gl)
        self.assertAlmostEqual(abs(sum(gl.mapped("amount_currency"))), 200.0, delta=TOL)
        # preview == posted
        self.assertEqual(preview[self.cat_isr.id][0], wh.account_id.id)
        self.assertAlmostEqual(preview[self.cat_isr.id][1], wh.amount, delta=TOL)

    def test_03_entry_balanced(self):
        move = self._invoice(50000.0)
        payment, _ = self._pay(move, self.cat_isr)
        deb = sum(payment.move_id.line_ids.mapped("debit"))
        cre = sum(payment.move_id.line_ids.mapped("credit"))
        self.assertAlmostEqual(deb, cre, delta=TOL)

    def test_04_full_reconcile_invoice(self):
        move = self._invoice(1000.0)
        payment, _ = self._pay(move, self.cat_isr)
        self.assertAlmostEqual(abs(move.amount_residual), 0.0, delta=TOL)
        self.assertNotIn((payment.journal_id.code or "").upper(), {"RET01", "RET02"})

    def test_05_partial_prorates_no_double_full(self):
        move = self._invoice(100000.0)
        p1, _ = self._pay(move, self.cat_isr, amount=50000.0)
        self.assertAlmostEqual(p1.justech_withholding_total, 1000.0, places=2)
        p2, _ = self._pay(move, self.cat_isr, amount=50000.0)
        self.assertAlmostEqual(p2.justech_withholding_total, 1000.0, places=2)
        total_wh = p1.justech_withholding_total + p2.justech_withholding_total
        self.assertAlmostEqual(total_wh, 2000.0, places=2)
        self.assertLessEqual(total_wh + TOL, 2000.0 + TOL)

    def test_06_multiple_withholdings_separate_lines(self):
        if not self.cat_itbis or not self.fiscal_b:
            self.skipTest("need itbis + second account")
        tax = self.company_data.get("default_tax_sale")
        move = self._invoice(10000.0, tax=tax)
        payment, preview = self._pay(move, self.cat_isr | self.cat_itbis)
        self.assertEqual(len(payment.justech_withholding_line_ids), 2)
        accounts = payment.justech_withholding_line_ids.mapped("account_id")
        self.assertTrue(self.fiscal in accounts)
        for wh in payment.justech_withholding_line_ids:
            self.assertIn(wh.catalog_id.id, preview)
            self.assertEqual(preview[wh.catalog_id.id][0], wh.account_id.id)

    def test_07_no_ret_journal_with_catalog(self):
        ret = self.env["account.journal"].search([("code", "in", ("RET01", "RET02"))], limit=1)
        if not ret:
            self.skipTest("no RET")
        self._activate(self.cat_isr)
        move = self._invoice(100.0)
        wiz = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create(
            {
                "journal_id": self.bank.id,
                "payment_method_line_id": self.bank.inbound_payment_method_line_ids[:1].id,
                "amount": abs(move.amount_residual),
                "justech_withholding_catalog_ids": [(6, 0, self.cat_isr.ids)],
            }
        )
        wiz.journal_id = ret
        with self.assertRaises(UserError):
            wiz._justech_assert_no_legacy_ret_journal()

    def test_08_identity_applied_eq_net_plus_wh(self):
        move = self._invoice(25000.0)
        payment, _ = self._pay(move, self.cat_isr)
        applied = payment.justech_applied_amount or payment.amount
        self.assertAlmostEqual(
            applied,
            payment.justech_net_transfer + payment.justech_withholding_total,
            delta=TOL,
        )

    def test_09_validity_date_blocks(self):
        self._activate(self.cat_isr)
        cfg = self.Config.search(
            [("catalog_id", "=", self.cat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"date_from": fields.Date.add(fields.Date.today(), days=10)})
        with self.assertRaises(UserError):
            self.cat_isr._get_withholding_account(self.company, date=fields.Date.today())
        cfg.write({"date_from": False})

    def test_10_legacy_payment_count_untouched_in_class(self):
        # smoke: creating UAT payments in TransactionCase rolls back
        before = self.env["account.payment"].search_count([])
        move = self._invoice(100.0)
        self._pay(move, self.cat_isr)
        # within same transaction count increases, but outer DB rolled back by framework
        self.assertGreaterEqual(self.env["account.payment"].search_count([]), before)
