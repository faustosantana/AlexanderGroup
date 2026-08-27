# -*- coding: utf-8 -*-
"""P2 — Segregación Recuperación Contable."""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_accounting_recovery.models.accounting_recovery_guard import (
    GROUP_ACCOUNTING_RECOVERY,
)


@tagged("post_install", "-at_install", "justech_accounting_recovery")
class TestAccountingRecoverySoD(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.recovery_group = cls.env.ref(GROUP_ACCOUNTING_RECOVERY)
        cls.invoice_group = cls.env.ref("account.group_account_invoice")
        cls.account_user_group = cls.env.ref("account.group_account_user")

        # Setup técnico: cascadas ORM pueden invocar button_draft.
        cls.env.user.sudo().write({"group_ids": [Command.link(cls.recovery_group.id)]})

        base_groups = [
            cls.env.ref("base.group_user").id,
            cls.invoice_group.id,
            cls.account_user_group.id,
        ]
        cls.user_no_recovery = cls.env["res.users"].create(
            {
                "name": "Contable Sin Recuperación",
                "login": "p2_no_recovery@test.justech",
                "email": "p2_no_recovery@test.justech",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "group_ids": [Command.set(base_groups)],
            }
        )
        cls.user_recovery = cls.env["res.users"].create(
            {
                "name": "Contable Con Recuperación",
                "login": "p2_recovery@test.justech",
                "email": "p2_recovery@test.justech",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "group_ids": [
                    Command.set(base_groups + [cls.recovery_group.id])
                ],
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {"name": "P2 SoD Partner", "company_id": cls.company.id}
        )

        accounts = cls.env["account.account"].search(
            [
                ("account_type", "in", ("expense", "income")),
                ("company_ids", "in", [cls.company.id]),
            ],
            limit=20,
        )
        expense = accounts.filtered(lambda a: a.account_type == "expense")[:1]
        income = accounts.filtered(lambda a: a.account_type == "income")[:1]
        if not expense or not income:
            expense = cls.env["account.account"].search(
                [("account_type", "=", "expense")], limit=1
            )
            income = cls.env["account.account"].search(
                [("account_type", "=", "income")], limit=1
            )
        if not expense or not income:
            raise AssertionError("Se requieren cuentas expense e income.")
        cls.account_debit = expense
        cls.account_credit = income

        cls.misc_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.misc_journal:
            raise AssertionError("Se requiere diario general.")

        bank = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not bank:
            raise AssertionError("Se requiere diario bank/cash.")
        cls.bank_journal = bank
        cls.payment_method = (
            bank.inbound_payment_method_line_ids[:1]
            or bank.outbound_payment_method_line_ids[:1]
        )
        if not cls.payment_method:
            raise AssertionError("Se requiere payment_method_line.")

    def _posted_misc_move(self):
        """Asiento misc (sin NCF) para no depender de validación fiscal."""
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SOD",
                "line_ids": [
                    Command.create(
                        {
                            "name": "P2 debit",
                            "account_id": self.account_debit.id,
                            "debit": 10.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "P2 credit",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 10.0,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        return move

    def _posted_payment(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 25.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 SoD payment",
            }
        )
        payment.action_post()
        return payment

    def test_group_exists_and_not_implied_by_invoice(self):
        self.assertTrue(self.recovery_group)
        self.assertEqual(self.recovery_group.name, "Recuperación Contable")
        self.assertNotIn(self.recovery_group, self.invoice_group.implied_ids)
        self.assertFalse(self.user_no_recovery.has_group(GROUP_ACCOUNTING_RECOVERY))
        self.assertTrue(self.user_recovery.has_group(GROUP_ACCOUNTING_RECOVERY))

    def test_denied_button_draft_without_group(self):
        move = self._posted_misc_move()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no_recovery).button_draft()
        self.assertEqual(move.state, "posted")

    def test_allowed_button_draft_with_group(self):
        move = self._posted_misc_move()
        move.with_user(self.user_recovery).button_draft()
        self.assertEqual(move.state, "draft")

    def test_denied_button_cancel_without_group(self):
        move = self._posted_misc_move()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no_recovery).button_cancel()
        self.assertEqual(move.state, "posted")

    def test_allowed_button_cancel_with_group(self):
        move = self._posted_misc_move()
        move.with_user(self.user_recovery).button_cancel()
        self.assertEqual(move.state, "cancel")

    def test_denied_payment_action_draft_without_group(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no_recovery).action_draft()

    def test_allowed_payment_action_draft_with_group(self):
        payment = self._posted_payment()
        payment.with_user(self.user_recovery).action_draft()
        self.assertEqual(payment.state, "draft")

    def test_denied_payment_action_cancel_without_group(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no_recovery).action_cancel()

    def test_allowed_payment_action_cancel_with_group(self):
        payment = self._posted_payment()
        payment.with_user(self.user_recovery).action_cancel()
        self.assertEqual(payment.state, "canceled")

    def test_denied_reverse_moves_without_group(self):
        move = self._posted_misc_move()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no_recovery)._reverse_moves()

    def test_normal_post_still_works_without_recovery(self):
        Move = self.env["account.move"].with_user(self.user_no_recovery)
        move = Move.create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SOD-NORMAL",
                "line_ids": [
                    Command.create(
                        {
                            "name": "ok debit",
                            "account_id": self.account_debit.id,
                            "debit": 5.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "ok credit",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 5.0,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_normal_payment_post_still_works_without_recovery(self):
        """P2.4: action_post de pago no debe disparar AccessError SoD."""
        payment = (
            self.env["account.payment"]
            .with_user(self.user_no_recovery)
            .create(
                {
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": self.partner.id,
                    "amount": 1.0,
                    "currency_id": self.company.currency_id.id,
                    "journal_id": self.bank_journal.id,
                    "payment_method_line_id": self.payment_method.id,
                    "date": "2026-07-21",
                    "memo": "P2-SOD-PAY-OK",
                }
            )
        )
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid", "posted"))

    def test_denied_unlink_draft_payment_without_group(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 8.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 draft unlink deny",
            }
        )
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no_recovery).unlink()
        self.assertTrue(payment.exists())

    def test_allowed_unlink_draft_payment_with_group(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 8.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 draft unlink ok",
            }
        )
        payment.with_user(self.user_recovery).unlink()
        self.assertFalse(payment.exists())

    def test_denied_unlink_draft_move_without_group(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SOD-UL",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 6.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 6.0,
                        }
                    ),
                ],
            }
        )
        with self.assertRaises(AccessError):
            move.with_user(self.user_no_recovery).unlink()
        self.assertTrue(move.exists())

    def test_allowed_unlink_draft_move_with_group(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SOD-UL-OK",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 6.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 6.0,
                        }
                    ),
                ],
            }
        )
        move.with_user(self.user_recovery).unlink()
        self.assertFalse(move.exists())