# -*- coding: utf-8 -*-
"""Fase 1 — catálogo global + company.config + resolución fail-closed."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_l10n_do_payments_withholding.models.withholding_account_validation import (
    assert_withholding_account_allowed,
)


@tagged("post_install", "-at_install", "justech_withholding_phase1")
class TestWithholdingPhase1(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Catalog = cls.env["justech.do.withholding.catalog"]
        cls.Config = cls.env["justech.do.withholding.company.config"]
        cls.company = cls.env.company
        cls.companies = cls.env["res.company"].search([])
        # Sync catalog once for tests
        cls.Catalog.with_context(justech_sync_uat_withholdings=True).sync_catalog_from_taxes(
            cls.company
        )
        cls.Catalog.ensure_company_configs()
        cls.uat_isr = cls.Catalog.search([("code", "=", "UAT-RET-ISR-2")], limit=1)
        cls.uat_itbis = cls.Catalog.search([("code", "=", "UAT-RET-ITBIS-30")], limit=1)
        # Fiscal liability-like account (not liquidity)
        Account = cls.env["account.account"]
        cls.fiscal_account = Account.search(
            [
                ("account_type", "in", ("liability_non_current", "liability_current", "asset_current")),
                ("active", "=", True),
            ],
            limit=1,
        )
        if cls.company and "company_ids" in Account._fields:
            acc = Account.search(
                [
                    ("account_type", "=", "liability_non_current"),
                    ("active", "=", True),
                    "|",
                    ("company_ids", "in", cls.company.id),
                    ("company_ids", "=", False),
                ],
                limit=1,
            )
            if acc:
                cls.fiscal_account = acc
        cls.cash_account = Account.search(
            [("account_type", "=", "asset_cash"), ("active", "=", True)],
            limit=1,
        )

    def test_01_catalog_materialized(self):
        self.assertTrue(self.Catalog.search_count([("company_id", "=", False)]) >= 8)
        self.assertTrue(self.uat_isr)
        self.assertTrue(self.uat_itbis)

    def test_02_configs_for_all_companies(self):
        globals_c = self.Catalog.search([("company_id", "=", False)])
        for cat in globals_c:
            for company in self.companies:
                cfg = self.Config.search(
                    [("catalog_id", "=", cat.id), ("company_id", "=", company.id)],
                    limit=1,
                )
                self.assertTrue(cfg, f"Missing config {cat.code} / {company.name}")

    def test_03_initial_pending_inactive_no_account(self):
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        # DEV puede tener UAT demo activa: forzar estado pendiente dentro del savepoint del test.
        cfg.write({"account_id": False, "active_config": False})
        self.assertFalse(cfg.account_id)
        self.assertFalse(cfg.active_config)
        self.assertEqual(cfg.state, "pending")

    def test_04_idempotent_ensure(self):
        before = self.Config.search_count([])
        self.Catalog.ensure_company_configs()
        after = self.Config.search_count([])
        self.assertEqual(before, after)

    def test_05_activate_without_account_blocked(self):
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": False, "active_config": False})
        with self.assertRaises(UserError):
            cfg.action_activate()
    def test_06_cash_account_blocked(self):
        if not self.cash_account:
            self.skipTest("No cash account")
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        with self.assertRaises(ValidationError):
            cfg.write({"account_id": self.cash_account.id})

    def test_07_configure_and_activate_valid(self):
        if not self.fiscal_account:
            self.skipTest("No fiscal account")
        ok, _, _ = assert_withholding_account_allowed(
            self.fiscal_account, self.company, raise_exception=False
        )
        if not ok:
            self.skipTest("Fiscal account not allowed by validator")
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": self.fiscal_account.id, "active_config": False})
        self.assertIn(cfg.state, ("inactive", "configured", "pending"))
        cfg.action_activate()
        self.assertTrue(cfg.active_config)
        self.assertEqual(cfg.state, "configured")
        acc = self.uat_isr._get_withholding_account(self.company)
        self.assertEqual(acc, self.fiscal_account)
        # cleanup — deactivate for other tests
        cfg.action_deactivate()

    def test_08_resolution_fail_closed_pending(self):
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_itbis.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": False, "active_config": False})
        with self.assertRaises(UserError):
            self.uat_itbis._get_withholding_account(self.company)

    def test_09_new_company_bootstrap(self):
        company = self.env["res.company"].create(
            {"name": "UAT WH Phase1 Co", "currency_id": self.company.currency_id.id}
        )
        globals_c = self.Catalog.with_context(active_test=False).search(
            [("company_id", "=", False)]
        )
        for cat in globals_c:
            cfg = self.Config.search(
                [("catalog_id", "=", cat.id), ("company_id", "=", company.id)],
                limit=1,
            )
            self.assertTrue(cfg)
            self.assertFalse(cfg.active_config)
            self.assertFalse(cfg.account_id)
        # No unlink: otras tablas (helpdesk) pueden referenciar la compañía.

    def test_10_no_duplicate_config(self):
        before = self.Config.search_count(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)]
        )
        self.assertEqual(before, 1)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Config.create(
                    {
                        "catalog_id": self.uat_isr.id,
                        "company_id": self.company.id,
                    }
                )

    def test_11_nature_visible(self):
        if not self.fiscal_account:
            self.skipTest("No fiscal account")
        ok, _, _ = assert_withholding_account_allowed(
            self.fiscal_account, self.company, raise_exception=False
        )
        if not ok:
            self.skipTest("skip")
        cfg = self.Config.search(
            [("catalog_id", "=", self.uat_isr.id), ("company_id", "=", self.company.id)],
            limit=1,
        )
        cfg.write({"account_id": self.fiscal_account.id})
        self.assertTrue(cfg.account_nature)
        cfg.write({"account_id": False})

    def test_12_legacy_ret_flag(self):
        Payment = self.env["account.payment"]
        Journal = self.env["account.journal"]
        ret = Journal.search([("code", "in", ("RET01", "RET02"))], limit=1)
        if not ret:
            self.skipTest("No RET journal")
        # Only compute on existing payment if any
        pay = Payment.search([("journal_id", "=", ret.id)], limit=1)
        if not pay:
            self.skipTest("No legacy payment")
        self.assertTrue(pay.justech_legacy_ret_journal)
        self.assertTrue(pay.justech_legacy_ret_warning)

    def test_13_payment_has_mail_mixins(self):
        Payment = self.env["account.payment"]
        self.assertTrue(
            any("mail.thread" in (i or "") or "mail.activity" in (i or "") for i in Payment._inherit)
            or hasattr(Payment, "message_post")
        )
        self.assertTrue(hasattr(Payment, "activity_ids"))
        self.assertTrue(hasattr(Payment, "message_follower_ids"))

    def test_14_catalog_has_chatter(self):
        self.assertTrue(hasattr(self.Catalog, "message_post"))
        self.assertTrue(hasattr(self.Config, "activity_schedule"))

    def test_15_wizard_create_missing(self):
        wiz = self.env["justech.withholding.config.wizard"].create({})
        wiz.action_create_missing_configs()
