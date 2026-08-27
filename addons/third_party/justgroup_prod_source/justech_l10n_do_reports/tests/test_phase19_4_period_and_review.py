"""Tests Fase 19.4 — período YYYYMM y revisión fiscal visible."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPhase194PeriodAndReview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.period_util = cls.env["justech.do.dgii.period"]
        cls.company = cls.env.company

    def test_period_202606_bounds(self):
        date_from, date_to = self.period_util.period_bounds_from_code("202606")
        self.assertEqual(date_from, date(2026, 6, 1))
        self.assertEqual(date_to, date(2026, 6, 30))

    def test_period_202602_non_leap(self):
        date_from, date_to = self.period_util.period_bounds_from_code("202602")
        self.assertEqual(date_from, date(2026, 2, 1))
        self.assertEqual(date_to, date(2026, 2, 28))

    def test_period_202402_leap(self):
        date_from, date_to = self.period_util.period_bounds_from_code("202402")
        self.assertEqual(date_from, date(2024, 2, 1))
        self.assertEqual(date_to, date(2024, 2, 29))

    def test_invalid_period_raises(self):
        with self.assertRaises(UserError):
            self.period_util.period_bounds_from_code("202613")
        with self.assertRaises(UserError):
            self.period_util.period_bounds_from_code("abcd12")

    def test_wizard_default_period_full_month(self):
        wiz = self.env["justech.do.fiscal.report.wizard"].create(
            {"report_type": "606", "company_id": self.company.id}
        )
        self.assertTrue(wiz.period_code)
        self.assertLess(wiz.date_from, wiz.date_to)
        self.assertEqual(wiz.date_from.day, 1)

    def test_wizard_onchange_period(self):
        wiz = self.env["justech.do.fiscal.report.wizard"].new(
            {"report_type": "606", "company_id": self.company.id}
        )
        wiz.period_code = "202606"
        wiz._onchange_period_code()
        self.assertEqual(wiz.date_from, date(2026, 6, 1))
        self.assertEqual(wiz.date_to, date(2026, 6, 30))

    def test_save_review_creates_persistent_report(self):
        wiz = self.env["justech.do.fiscal.report.wizard"].create(
            {
                "report_type": "606",
                "company_id": self.company.id,
                "period_code": "202606",
                "date_from": date(2026, 6, 1),
                "date_to": date(2026, 6, 30),
            }
        )
        wiz.action_validate()
        action = wiz.action_save_review()
        report = self.env["justech.do.fiscal.report"].browse(action["res_id"])
        self.assertTrue(report.exists())
        self.assertTrue(report.line_ids)
        self.assertIn(report.state, ("validated", "draft"))

    def test_excluded_moves_visible_in_review(self):
        excluded_move = self.env["account.move"].search(
            [
                ("company_id", "=", self.company.id),
                ("justech_do_include_in_dgii", "=", False),
                ("state", "=", "posted"),
            ],
            limit=1,
        )
        if not excluded_move:
            self.skipTest("Sin facturas excluidas en TEST para validar visibilidad")
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.4 excluded visibility",
                "report_type": "606",
                "date_from": excluded_move.invoice_date.replace(day=1),
                "date_to": excluded_move.invoice_date,
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        excluded_lines = report.line_ids.filtered(
            lambda l: l.move_id == excluded_move
        )
        self.assertTrue(excluded_lines)
        self.assertIn(
            excluded_lines.fiscal_state,
            ("excluded", "cancelled"),
        )
        self.assertTrue(excluded_lines.exclusion_reason)
