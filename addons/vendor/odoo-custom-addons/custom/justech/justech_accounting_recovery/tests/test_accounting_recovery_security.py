# -*- coding: utf-8 -*-
"""P2 security — bypass audit (context / RPC / server action / unlink)."""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_accounting_recovery.models.accounting_recovery_guard import (
    GROUP_ACCOUNTING_RECOVERY,
    in_payment_unlink_cascade,
    payment_unlink_cascade_enter,
    payment_unlink_cascade_exit,
)

CTX_LEGACY = "justech_recovery_from_payment_unlink"
CTX_FAKE = "justech_allow_recovery_bypass"


@tagged(
    "post_install",
    "-at_install",
    "justech_accounting_recovery",
    "justech_recovery_security",
)
class TestAccountingRecoveryBypassAudit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.recovery_group = cls.env.ref(GROUP_ACCOUNTING_RECOVERY)
        cls.invoice_group = cls.env.ref("account.group_account_invoice")
        cls.account_user_group = cls.env.ref("account.group_account_user")
        cls.env.user.sudo().write({"group_ids": [Command.link(cls.recovery_group.id)]})

        base_groups = [
            cls.env.ref("base.group_user").id,
            cls.invoice_group.id,
            cls.account_user_group.id,
        ]
        cls.user_no = cls.env["res.users"].create(
            {
                "name": "P2 Sec No Recovery",
                "login": "p2_sec_no@test.justech",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "group_ids": [Command.set(base_groups)],
            }
        )
        cls.user_yes = cls.env["res.users"].create(
            {
                "name": "P2 Sec Recovery",
                "login": "p2_sec_yes@test.justech",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "group_ids": [Command.set(base_groups + [cls.recovery_group.id])],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "P2 Sec Partner", "company_id": cls.company.id}
        )
        cls.account_debit = cls.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1
        )
        cls.account_credit = cls.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        cls.misc_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        bank = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.bank_journal = bank
        cls.payment_method = (
            bank.inbound_payment_method_line_ids[:1]
            or bank.outbound_payment_method_line_ids[:1]
        )

    def _posted_misc(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SEC",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 10.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 10.0,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def _posted_payment(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 33.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 sec pay",
            }
        )
        payment.action_post()
        return payment

    def _draft_payment(self):
        return self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 11.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 draft pay",
            }
        )

    # --- unauthorized direct ---
    def test_unauth_button_draft(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).button_draft()

    def test_unauth_button_cancel(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).button_cancel()

    def test_unauth_action_reverse(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).action_reverse()

    def test_unauth_reverse_moves(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no)._reverse_moves()

    def test_unauth_reversal_wizard(self):
        move = self._posted_misc()
        wiz = (
            self.env["account.move.reversal"]
            .with_user(self.user_no)
            .with_context(active_model="account.move", active_ids=move.ids)
            .create(
                {
                    "journal_id": move.journal_id.id,
                    "date": move.date,
                }
            )
        )
        wiz.move_ids = move
        with self.assertRaises(AccessError):
            wiz.reverse_moves()

    def test_unauth_payment_action_draft(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).action_draft()

    def test_unauth_payment_action_cancel(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).action_cancel()

    def test_unauth_payment_button_request_cancel(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).button_request_cancel()

    # --- context bypass must stay blocked ---
    def test_context_bypass_button_draft_blocked(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True, CTX_FAKE: True}
            ).button_draft()

    def test_context_bypass_reverse_moves_blocked(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True}
            )._reverse_moves()

    def test_context_bypass_payment_draft_blocked(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True}
            ).action_draft()

    def test_context_bypass_payment_cancel_blocked(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True}
            ).action_cancel()

    def test_context_bypass_unlink_posted_blocked(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True}
            ).unlink()

    # --- RPC-equivalent: plain method calls as other user ---
    def test_rpc_equivalent_button_draft_blocked(self):
        """JSON/XML-RPC ejecutan el mismo método con el uid de sesión."""
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(self.user_no).browse(move.id).button_draft()

    def test_rpc_equivalent_payment_cancel_blocked(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            self.env["account.payment"].with_user(self.user_no).browse(
                payment.id
            ).action_cancel()

    # --- server action style: execute code that only calls public methods ---
    def test_server_action_style_button_draft_blocked(self):
        move = self._posted_misc()
        Action = self.env["ir.actions.server"].with_user(self.user_no)
        action = Action.sudo().create(
            {
                "name": "P2 try draft",
                "model_id": self.env["ir.model"]._get("account.move").id,
                "state": "code",
                "code": "records.button_draft()",
            }
        )
        with self.assertRaises(AccessError):
            action.with_user(self.user_no).with_context(
                active_model="account.move",
                active_ids=move.ids,
                active_id=move.id,
            ).run()

    def test_server_action_style_payment_cancel_blocked(self):
        payment = self._posted_payment()
        action = (
            self.env["ir.actions.server"]
            .sudo()
            .create(
                {
                    "name": "P2 try cancel pay",
                    "model_id": self.env["ir.model"]._get("account.payment").id,
                    "state": "code",
                    "code": "records.action_cancel()",
                }
            )
        )
        with self.assertRaises(AccessError):
            action.with_user(self.user_no).with_context(
                active_model="account.payment",
                active_ids=payment.ids,
                active_id=payment.id,
            ).run()

    # --- unlink ---
    def test_unauth_unlink_posted_payment_blocked(self):
        payment = self._posted_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).unlink()

    def test_unauth_unlink_draft_payment_blocked(self):
        payment = self._draft_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).unlink()
        self.assertTrue(payment.exists())

    def test_unauth_unlink_draft_move_blocked(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SEC-DRAFT-UL",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 3.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 3.0,
                        }
                    ),
                ],
            }
        )
        self.assertEqual(move.state, "draft")
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).unlink()
        self.assertTrue(move.exists())

    def test_unauth_unlink_posted_move_blocked(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).unlink()
        self.assertTrue(move.exists())

    def test_auth_unlink_draft_move_allowed(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SEC-DRAFT-UL-OK",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 2.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 2.0,
                        }
                    ),
                ],
            }
        )
        move.with_user(self.user_yes).unlink()
        self.assertFalse(move.exists())

    def test_unauth_create_payment_ok(self):
        payment = self.env["account.payment"].with_user(self.user_no).create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 21.0,
                "currency_id": self.company.currency_id.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.payment_method.id,
                "date": "2026-07-20",
                "memo": "P2 normal pay",
            }
        )
        self.assertTrue(payment.id)
        self.assertEqual(payment.state, "draft")

    def test_auth_unlink_posted_payment_allowed(self):
        payment = self._posted_payment()
        payment.with_user(self.user_yes).unlink()
        self.assertFalse(payment.exists())

    def test_auth_unlink_draft_payment_allowed(self):
        payment = self._draft_payment()
        payment.with_user(self.user_yes).unlink()
        self.assertFalse(payment.exists())

    def test_context_bypass_unlink_draft_payment_blocked(self):
        payment = self._draft_payment()
        with self.assertRaises(AccessError):
            payment.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True, CTX_FAKE: True}
            ).unlink()

    def test_context_bypass_unlink_draft_move_blocked(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SEC-CTX-UL",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 1.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 1.0,
                        }
                    ),
                ],
            }
        )
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).with_context(
                **{CTX_LEGACY: True}
            ).unlink()
    # --- cascade: statement undo entry sets thread-local; context does not ---
    def test_thread_local_not_set_by_context(self):
        self.assertFalse(in_payment_unlink_cascade())
        self.env["account.move"].with_context(**{CTX_LEGACY: True})
        self.assertFalse(in_payment_unlink_cascade())

    def test_cascade_enter_exit_roundtrip(self):
        self.assertFalse(in_payment_unlink_cascade())
        payment_unlink_cascade_enter()
        self.assertTrue(in_payment_unlink_cascade())
        payment_unlink_cascade_exit()
        self.assertFalse(in_payment_unlink_cascade())

    def test_cascade_skips_button_cancel_check(self):
        """Con flag de cascada armado, button_cancel no exige el grupo."""
        move = self._posted_misc()
        payment_unlink_cascade_enter()
        try:
            move.with_user(self.user_no).button_cancel()
        finally:
            payment_unlink_cascade_exit()
        self.assertEqual(move.state, "cancel")

    def test_cascade_skips_button_draft_check(self):
        move = self._posted_misc()
        payment_unlink_cascade_enter()
        try:
            move.with_user(self.user_no).button_draft()
        finally:
            payment_unlink_cascade_exit()
        self.assertEqual(move.state, "draft")

    def test_statement_undo_wrapper_arms_cascade(self):
        """El wrapper de action_undo_reconciliation arma y desarma el flag."""
        Line = self.env["account.bank.statement.line"]
        self.assertFalse(in_payment_unlink_cascade())
        Line.action_undo_reconciliation()
        self.assertFalse(in_payment_unlink_cascade())

    # --- authorized ---
    def test_auth_button_draft(self):
        move = self._posted_misc()
        move.with_user(self.user_yes).button_draft()
        self.assertEqual(move.state, "draft")

    def test_auth_button_cancel(self):
        move = self._posted_misc()
        move.with_user(self.user_yes).button_cancel()
        self.assertEqual(move.state, "cancel")

    def test_auth_payment_action_cancel(self):
        payment = self._posted_payment()
        payment.with_user(self.user_yes).action_cancel()
        self.assertEqual(payment.state, "canceled")

    def test_auth_payment_action_draft(self):
        payment = self._posted_payment()
        payment.with_user(self.user_yes).action_draft()
        self.assertEqual(payment.state, "draft")

    def test_auth_reverse_moves(self):
        move = self._posted_misc()
        moves = move.with_user(self.user_yes)._reverse_moves()
        self.assertTrue(moves)

    # --- regression ---
    def test_unauth_create_post_misc_ok(self):
        Move = self.env["account.move"].with_user(self.user_no)
        move = Move.create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": "2026-07-20",
                "ref": "P2-SEC-OK",
                "line_ids": [
                    Command.create(
                        {
                            "name": "d",
                            "account_id": self.account_debit.id,
                            "debit": 4.0,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "c",
                            "account_id": self.account_credit.id,
                            "debit": 0.0,
                            "credit": 4.0,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_sudo_same_user_still_blocked(self):
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).sudo().button_draft()

    # --- P2.4: empty recordset / payment post regression ---
    def test_empty_button_cancel_without_group_ok(self):
        """No-op ORM: cancel sobre [] no exige Recuperación Contable."""
        self.env["account.move"].with_user(self.user_no).browse([]).button_cancel()

    def test_empty_button_draft_without_group_ok(self):
        self.env["account.move"].with_user(self.user_no).browse([]).button_draft()

    def test_empty_payment_action_cancel_without_group_ok(self):
        self.env["account.payment"].with_user(self.user_no).browse([]).action_cancel()

    def test_empty_payment_action_draft_without_group_ok(self):
        self.env["account.payment"].with_user(self.user_no).browse([]).action_draft()

    def test_unauth_payment_action_post_ok(self):
        """Regresión P2.4: publicar pago sin grupo no debe fallar por SoD."""
        payment = (
            self.env["account.payment"]
            .with_user(self.user_no)
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
                    "memo": "P2.4-REG",
                }
            )
        )
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid", "posted"))
        if payment.move_id:
            self.assertEqual(payment.move_id.state, "posted")

    def test_nonempty_button_cancel_still_blocked(self):
        """SoD intacto: cancel real sin grupo sigue denegado."""
        move = self._posted_misc()
        with self.assertRaises(AccessError):
            move.with_user(self.user_no).button_cancel()
