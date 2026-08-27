"""Tests Fase 20 — correcciones framework fiscal DGII."""
from datetime import date

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPhase20FiscalFramework(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.period_util = cls.env["justech.do.dgii.period"]
        cls.fiscal_user = cls.env["res.users"].create(
            {
                "name": "P20 Fiscal User",
                "login": f"p20_fiscal_{cls.env.cr.dbname}@test.com",
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
                "name": "P20 Supervisor",
                "login": f"p20_super_{cls.env.cr.dbname}@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(
                        cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager").id
                    ),
                    Command.link(cls.env.ref("account.group_account_invoice").id),
                ],
            }
        )

    def _period_bounds(self, code="202606"):
        return self.period_util.period_bounds_from_code(code)

    def _create_report(self, period_code="202606"):
        date_from, date_to = self._period_bounds(period_code)
        return self.env["justech.do.fiscal.report"].create(
            {
                "name": f"P20 {period_code}",
                "report_type": "606",
                "period_code": period_code,
                "date_from": date_from,
                "date_to": date_to,
                "company_id": self.company.id,
            }
        )

    def test_period_dates_from_yyyymm(self):
        report = self._create_report("202606")
        self.assertEqual(report.date_from, date(2026, 6, 1))
        self.assertEqual(report.date_to, date(2026, 6, 30))
        self.assertEqual(report.date_from_display, "01/06/2026")
        self.assertEqual(report.date_to_display, "30/06/2026")

    def test_state_guard_blocks_manual_change(self):
        report = self._create_report()
        with self.assertRaises(UserError):
            report.write({"state": "approved"})

    def test_workflow_transitions_logged(self):
        report = self._create_report()
        report.action_load_review_lines()
        report.action_validate_period()
        self.assertEqual(report.state, "validated")
        self.assertTrue(report.audit_ids.filtered(lambda a: a.event_type == "validate"))
        self.assertTrue(report.message_ids)

    def test_summary_counts_match_lines(self):
        report = self._create_report()
        report.action_load_review_lines()
        report._refresh_summary_counts()
        self.assertEqual(report.count_all, report.review_line_count)
        self.assertEqual(report.count_valid, report.review_valid_count)

    def test_pending_tray_domain_has_pending_flag(self):
        report = self._create_report()
        report.action_load_review_lines()
        line = report.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )[:1]
        if not line:
            self.skipTest("Sin línea válida")
        self.env["justech.do.dgii.report.exclude.wizard"].with_user(
            self.fiscal_user
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "P20 prueba bandeja",
            }
        ).action_confirm_exclude()
        report.invalidate_recordset()
        self.assertTrue(report.has_pending_approval)
        pending = self.env["justech.do.fiscal.report"].search(
            [("has_pending_approval", "=", True), ("id", "=", report.id)]
        )
        self.assertTrue(pending)

    def test_export_blocker_wizard_when_not_approved(self):
        report = self._create_report()
        report.action_load_review_lines()
        report.action_validate_period()
        line = report.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )[:1]
        if not line:
            self.skipTest("Sin línea válida")
        line.write(
            {
                "include_in_report": False,
                "manual_exclusion": True,
                "line_approval_state": "pending",
                "exclusion_reason": "P20 bloqueo",
                "fiscal_state": "excluded",
            }
        )
        report._refresh_summary_counts()
        action = report.with_user(self.supervisor)._check_can_generate()
        self.assertIsInstance(action, dict)
        self.assertEqual(
            action["res_model"], "justech.do.dgii.export.blocker.wizard"
        )
        ctx = action.get("context", {})
        self.assertIn("default_blocking_line_ids", ctx)

    def test_correction_returns_fiscal_review(self):
        report = self._create_report()
        report.action_load_review_lines()
        line = report.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )[:1]
        if not line:
            self.skipTest("Sin línea válida")
        self.env["justech.do.dgii.report.exclude.wizard"].with_user(
            self.fiscal_user
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "P20 corrección",
            }
        ).action_confirm_exclude()
        action = self.env["justech.do.dgii.report.reject.wizard"].with_user(
            self.supervisor
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "action_mode": "correction",
                "comment": "Corregir datos",
            }
        ).action_confirm_reject()
        self.assertEqual(action.get("res_model"), "justech.do.fiscal.report")
        self.assertEqual(report.state, "validated")

    def test_archive_legacy_report(self):
        legacy = self.env["justech.do.fiscal.report"].create(
            {
                "name": "606 — Compras 2026-06-30",
                "report_type": "606",
                "date_from": date(2026, 6, 1),
                "date_to": date(2026, 6, 30),
                "company_id": self.company.id,
                "state": "done",
                "generated_at": fields.Datetime.now(),
            }
        )
        self.env["justech.do.fiscal.report"]._archive_legacy_reports()
        self.assertFalse(legacy.active)

    def test_approve_line_workflow(self):
        report = self._create_report()
        report.action_load_review_lines()
        line = report.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )[:1]
        if not line:
            self.skipTest("Sin línea válida")
        self.env["justech.do.dgii.report.exclude.wizard"].with_user(
            self.fiscal_user
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "P20 aprobación línea",
            }
        ).action_confirm_exclude()
        line.with_user(self.supervisor).action_approve_line()
        report.invalidate_recordset()
        self.assertEqual(line.line_approval_state, "approved")
        self.assertEqual(report.state, "approved")
