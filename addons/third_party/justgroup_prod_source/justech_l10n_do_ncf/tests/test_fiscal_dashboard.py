# -*- coding: utf-8 -*-
"""Dashboard fiscal — solo lectura, agrupación por período original."""
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_fiscal_dashboard")
class TestFiscalDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Dash = cls.env["justech.do.fiscal.dashboard"]
        cls.Reg = cls.env["justech.do.fiscal.regularization"]
        cls.Move = cls.env["account.move"]
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.responsible = cls.env["res.users"].create(
            {
                "name": "Fiscal Dashboard Resp",
                "login": "fiscal.dash.%s" % id(cls),
                "email": "fiscal.dash@example.com",
            }
        )
        cls.company.justech_do_fiscal_regularization_user_id = cls.responsible.id

    def _make_reg(
        self,
        *,
        period,
        ncf,
        status_608="pending",
        general="pending",
        void_date=None,
        **extra,
    ):
        partner = self.env["res.partner"].create({"name": "Dash %s" % ncf})
        inv_day = date(int(period[:4]), int(period[4:6]), 15)
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": inv_day,
                "date": inv_day,
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 100})
                ],
            }
        )
        move.write(
            {
                "justech_do_ncf": ncf,
                "justech_do_ncf_voided": True,
                "justech_do_ncf_void_date": void_date or inv_day,
                "state": "cancel",
                "justech_do_608_reporting_period": period,
                "justech_do_original_fiscal_period": period,
            }
        )
        vals = {
            "company_id": self.company.id,
            "move_id": move.id,
            "ncf": ncf,
            "partner_id": partner.id,
            "invoice_date": move.invoice_date,
            "original_invoice_date": move.invoice_date,
            "original_fiscal_period": period,
            "reporting_period_608": period,
            "required_608": True,
            "status_608": status_608,
            "general_status": general,
            "responsible_user_id": self.responsible.id,
            "source_operation": "manual",
        }
        vals.update(extra)
        return self.Reg.create(vals)

    def test_open_dashboard_does_not_create_regs_or_activities(self):
        before_reg = self.Reg.search_count([])
        before_act = self.env["mail.activity"].search_count(
            [("res_model", "=", "justech.do.fiscal.regularization")]
        )
        action = self.Dash.action_open_dashboard()
        self.assertEqual(action["res_model"], "justech.do.fiscal.dashboard")
        dash = self.Dash.browse(action["res_id"])
        self.assertTrue(dash.exists())
        self.assertEqual(self.Reg.search_count([]), before_reg)
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "justech.do.fiscal.regularization")]
            ),
            before_act,
        )
        # refresh again still no side effects on business models
        dash.action_refresh()
        self.assertEqual(self.Reg.search_count([]), before_reg)

    def test_kpi_pending_608_matches_center(self):
        self._make_reg(period="202604", ncf="B0100002101", status_608="pending")
        self._make_reg(period="202604", ncf="B0100002102", status_608="accepted")
        self._make_reg(
            period="202607", ncf="B0100002103", status_608="rectification_required"
        )
        dash = self.Dash.create({"company_id": self.company.id})
        dash._refresh_metrics()
        expected = self.Reg.search_count(
            [
                ("company_id", "=", self.company.id),
                ("required_608", "=", True),
                (
                    "status_608",
                    "in",
                    ("pending", "rectification_required", "prepared", "exported"),
                ),
            ]
        )
        self.assertEqual(dash.kpi_pending_608, expected)
        self.assertGreaterEqual(dash.kpi_pending_608, 2)

    def test_period_grouping_uses_original_not_void_month(self):
        april = self._make_reg(
            period="202604",
            ncf="B0100002201",
            void_date=date(2026, 7, 28),
        )
        july = self._make_reg(period="202607", ncf="B0100002202")
        dash = self.Dash.create({"company_id": self.company.id})
        dash._refresh_metrics()
        by_period = {l.period_code: l for l in dash.period_line_ids}
        self.assertIn("202604", by_period)
        self.assertIn("202607", by_period)
        self.assertGreaterEqual(by_period["202604"].count_pending_608, 1)
        # Exporter: april voided in july belongs to april period only
        exporter = self.env["justech.do.dgii.608.exporter"]
        move = april.move_id
        self.assertTrue(
            exporter._move_in_608_period(move, date(2026, 4, 1), date(2026, 4, 30))
        )
        self.assertFalse(
            exporter._move_in_608_period(move, date(2026, 7, 1), date(2026, 7, 31))
        )
        self.assertTrue(
            exporter._move_in_608_period(
                july.move_id, date(2026, 7, 1), date(2026, 7, 31)
            )
        )

    def test_open_608_wizard_does_not_mark_presented(self):
        self._make_reg(period="202604", ncf="B0100002301")
        dash = self.Dash.create({"company_id": self.company.id})
        dash._refresh_metrics()
        if "justech.do.fiscal.report.wizard" not in self.env:
            self.skipTest("reports wizard missing")
        action = dash.action_open_608_wizard(period_code="202604")
        wiz = self.env["justech.do.fiscal.report.wizard"].browse(action["res_id"])
        self.assertEqual(wiz.report_type, "608")
        self.assertEqual(wiz.period_code, "202604")
        # Opening wizard must not flip regularization status
        reg = self.Reg.search([("ncf", "=", "B0100002301")], limit=1)
        self.assertEqual(reg.status_608, "pending")

    def test_historical_audit_read_only_no_backfill(self):
        partner = self.env["res.partner"].create({"name": "Mismatch"})
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": date(2026, 4, 13),
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 50})
                ],
            }
        )
        move.write(
            {
                "justech_do_ncf": "B0100002401",
                "justech_do_ncf_voided": True,
                "justech_do_ncf_void_date": date(2026, 7, 27),
                "state": "cancel",
            }
        )
        before_period = move.justech_do_608_reporting_period
        dash = self.Dash.create({"company_id": self.company.id})
        dash._refresh_metrics()
        self.assertGreaterEqual(dash.kpi_historical_review, 1)
        action = dash.action_open_historical_mismatch()
        self.assertEqual(action["res_model"], "justech.do.fiscal.dashboard.audit")
        move.invalidate_recordset()
        self.assertEqual(move.justech_do_608_reporting_period, before_period)
