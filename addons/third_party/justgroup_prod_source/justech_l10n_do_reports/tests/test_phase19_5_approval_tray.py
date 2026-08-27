"""Tests Fase 19.5 — bandeja global pendientes de aprobación."""
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPhase195ApprovalTray(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.fiscal_user = cls.env["res.users"].create(
            {
                "name": "P19.5 Fiscal User",
                "login": f"p195_fiscal_{cls.env.cr.dbname}@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(
                        cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_user").id
                    ),
                    Command.link(cls.env.ref("account.group_account_invoice").id),
                ],
            }
        )
        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "P19.5 Supervisor",
                "login": f"p195_super_{cls.env.cr.dbname}@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(
                        cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager").id
                    ),
                    Command.link(cls.env.ref("account.group_account_invoice").id),
                ],
            }
        )

    def _create_report_with_exclusion(self):
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.5 Tray test",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        line = report.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )[:1]
        if not line:
            self.skipTest("Sin línea válida para excluir")
        self.env["justech.do.dgii.report.exclude.wizard"].with_user(
            self.fiscal_user
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "P19.5 prueba bandeja",
            }
        ).action_confirm_exclude()
        return report, line

    def test_pending_tray_domain(self):
        report, _line = self._create_report_with_exclusion()
        pending = self.env["justech.do.fiscal.report"].search(
            [("has_pending_approval", "=", True)]
        )
        self.assertIn(report, pending)
        self.assertTrue(report.approval_submitted_by_id)
        self.assertTrue(report.pending_approval_count)

    def test_approve_line_removes_from_tray(self):
        report, line = self._create_report_with_exclusion()
        line.with_user(self.supervisor).action_approve_line()
        pending = self.env["justech.do.fiscal.report"].search(
            [("approval_ids.state", "=", "pending"), ("id", "=", report.id)]
        )
        self.assertFalse(pending)
        self.assertEqual(report.state, "approved")

    def test_reject_line_returns_to_validated(self):
        report, line = self._create_report_with_exclusion()
        self.env["justech.do.dgii.report.reject.wizard"].with_user(
            self.supervisor
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "action_mode": "correction",
                "comment": "Corregir datos fiscales",
            }
        ).action_confirm_reject()
        pending = self.env["justech.do.fiscal.report"].search(
            [("approval_ids.state", "=", "pending"), ("id", "=", report.id)]
        )
        self.assertFalse(pending)
        self.assertEqual(report.state, "validated")
        line.move_id.invalidate_recordset()
        self.assertTrue(line.move_id.justech_do_include_in_dgii)

    def test_fiscal_user_cannot_approve_line(self):
        report, line = self._create_report_with_exclusion()
        with self.assertRaises(AccessError):
            line.with_user(self.fiscal_user).action_approve_line()
