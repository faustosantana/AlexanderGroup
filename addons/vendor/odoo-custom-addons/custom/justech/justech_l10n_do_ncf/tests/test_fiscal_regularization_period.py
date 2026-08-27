# -*- coding: utf-8 -*-
"""Regularización fiscal: período original 608 / 607 / actividad."""
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_fiscal_regularization")
class TestFiscalRegularizationOriginalPeriod(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.svc = cls.env["justech.do.fiscal.regularization.service"]
        cls.Move = cls.env["account.move"]
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.responsible = cls.env["res.users"].create(
            {
                "name": "Florangel Rodríguez Test",
                "login": "florangel.test.%s" % id(cls),
                "email": "florangel.test@example.com",
            }
        )
        cls.company.justech_do_fiscal_regularization_user_id = cls.responsible.id

    def _make_cancelled_invoice(self, *, invoice_date, ncf, included_607=False):
        partner = self.env["res.partner"].create({"name": "Cliente %s" % ncf})
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Linea prueba",
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        move.write(
            {
                "justech_do_ncf": ncf,
                "justech_do_ncf_voided": True,
                "justech_do_ncf_cancel_type": "01",
                "justech_do_ncf_void_date": date(2026, 7, 28),
                "justech_do_ncf_void_reason": "No entregado al cliente",
                "justech_do_included_in_607": included_607,
                "justech_do_cancellation_method": "direct_cancel",
                "state": "cancel",
            }
        )
        return move

    def test_april_invoice_cancelled_in_july_uses_april_period(self):
        move = self._make_cancelled_invoice(
            invoice_date=date(2026, 4, 15),
            ncf="B0100001500",
            included_607=True,
        )
        with patch.object(
            type(self.svc),
            "_find_607_report_period",
            return_value=(True, "202604"),
        ):
            reg = self.svc.ensure_regularization_for_move(
                move,
                reason="Prueba abril",
                cancel_type="01",
                source_operation="direct_cancel",
            )
        self.assertEqual(reg.original_fiscal_period, "202604")
        self.assertEqual(reg.reporting_period_608, "202604")
        self.assertEqual(reg.rectification_607_period, "202604")
        self.assertTrue(reg.rectification_607_required)
        self.assertEqual(move.justech_do_608_reporting_period, "202604")
        self.assertNotEqual(reg.reporting_period_608, "202607")
        self.assertEqual(reg.responsible_user_id, self.responsible)
        activity = reg.activity_id or self.env["mail.activity"].search(
            [
                ("res_model", "=", "justech.do.fiscal.regularization"),
                ("res_id", "=", reg.id),
            ],
            limit=1,
        )
        self.assertTrue(activity)
        self.assertIn("04/2026", activity.summary)

    def test_july_invoice_uses_july_period(self):
        move = self._make_cancelled_invoice(
            invoice_date=date(2026, 7, 1), ncf="B0100001591"
        )
        reg = self.svc.ensure_regularization_for_move(
            move, reason="Prueba julio", cancel_type="01"
        )
        self.assertEqual(reg.original_fiscal_period, "202607")
        self.assertEqual(reg.reporting_period_608, "202607")

    def test_never_in_607_does_not_require_607_rectification(self):
        move = self._make_cancelled_invoice(
            invoice_date=date(2026, 5, 10),
            ncf="B0100001600",
            included_607=False,
        )
        with patch.object(
            type(self.svc), "_find_607_report_period", return_value=(False, False)
        ):
            reg = self.svc.ensure_regularization_for_move(
                move, reason="Sin 607", cancel_type="01"
            )
        self.assertFalse(reg.rectification_607_required)
        self.assertEqual(reg.status_607, "na")
        self.assertTrue(reg.required_608)
        self.assertEqual(reg.reporting_period_608, "202605")

    def test_no_duplicate_regularization(self):
        move = self._make_cancelled_invoice(
            invoice_date=date(2026, 6, 1), ncf="B0100001700"
        )
        r1 = self.svc.ensure_regularization_for_move(move, reason="a", cancel_type="01")
        r2 = self.svc.ensure_regularization_for_move(move, reason="b", cancel_type="01")
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(
            self.env["justech.do.fiscal.regularization"].search_count(
                [("move_id", "=", move.id)]
            ),
            1,
        )

    def test_608_exporter_filters_by_original_period_not_void_date(self):
        exporter = self.env["justech.do.dgii.608.exporter"]
        move = self.Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "state": "cancel",
                "invoice_date": date(2026, 4, 15),
                "justech_do_ncf": "B0100001800",
                "justech_do_ncf_voided": True,
                "justech_do_ncf_void_date": date(2026, 7, 28),
                "justech_do_608_reporting_period": "202604",
                "justech_do_original_fiscal_period": "202604",
            }
        )
        self.assertEqual(exporter._608_reporting_period(move), "202604")
        self.assertTrue(
            exporter._move_in_608_period(move, date(2026, 4, 1), date(2026, 4, 30))
        )
        self.assertFalse(
            exporter._move_in_608_period(move, date(2026, 7, 1), date(2026, 7, 31))
        )


@tagged("post_install", "-at_install", "justech_invoice_status")
class TestAnnulledBadgeNot608UntilPresented(TransactionCase):
    def test_cancelled_pending_shows_annulled_not_voided_608(self):
        Move = self.env["account.move"]
        move = Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.env.company.id,
                "state": "cancel",
                "justech_do_ncf": "B0100001591",
                "justech_do_ncf_voided": True,
                "justech_do_cancellation_method": "direct_cancel",
                "justech_do_fiscal_regularization_state": "pending_regularization",
            }
        )
        move._compute_justech_do_ui_statuses()
        self.assertEqual(move.justech_do_fiscal_ui_status, "annulled")
        labels = dict(
            move._fields["justech_do_fiscal_ui_status"]._description_selection(
                self.env
            )
        )
        self.assertEqual(labels.get("annulled"), "Anulado")
        self.assertEqual(labels.get("voided_608"), "Anulado (608)")

    def test_reported_608_shows_voided_608_badge(self):
        Move = self.env["account.move"]
        move = Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.env.company.id,
                "state": "cancel",
                "justech_do_ncf": "B0100001591",
                "justech_do_ncf_voided": True,
                "justech_do_fiscal_regularization_state": "reported_608",
            }
        )
        move._compute_justech_do_ui_statuses()
        self.assertEqual(move.justech_do_fiscal_ui_status, "voided_608")
