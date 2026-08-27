# -*- coding: utf-8 -*-
"""Backfill histórico de regularizaciones — preview idempotente."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_fiscal_backfill")
class TestFiscalHistoricalBackfill(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Move = cls.env["account.move"]
        cls.Reg = cls.env["justech.do.fiscal.regularization"]
        cls.Wiz = cls.env["justech.do.fiscal.historical.backfill.wizard"]
        cls.Svc = cls.env["justech.do.fiscal.regularization.service"]
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.responsible = cls.env["res.users"].create(
            {
                "name": "Backfill Resp",
                "login": "backfill.resp.%s" % id(cls),
                "email": "backfill@example.com",
            }
        )
        cls.company.justech_do_fiscal_regularization_user_id = cls.responsible.id
        # Admin fiscal for execute (Odoo 19: group_ids)
        manager = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        cls.env.user.write({"group_ids": [(4, manager.id)]})

    def _voided_move(
        self,
        *,
        name_ncf,
        invoice_day,
        void_day=None,
        cancel_type="04",
        state="cancel",
        period_fields=None,
    ):
        partner = self.env["res.partner"].create({"name": "BF %s" % name_ncf})
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": invoice_day,
                "date": invoice_day,
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 100})
                ],
            }
        )
        vals = {
            "justech_do_ncf": name_ncf,
            "justech_do_ncf_voided": True,
            "justech_do_ncf_void_date": void_day or invoice_day,
            "justech_do_ncf_cancel_type": cancel_type,
            "state": state,
            "justech_do_dgii_fiscal_state": "cancelled",
        }
        if period_fields:
            vals.update(period_fields)
        move.write(vals)
        return move

    def test_preview_does_not_write(self):
        move = self._voided_move(
            name_ncf="B0100004101",
            invoice_day=date(2026, 4, 15),
            void_day=date(2026, 7, 20),
        )
        before = self.Reg.search_count([])
        wiz = self.Wiz.create({"company_id": self.company.id})
        wiz.action_preview()
        self.assertEqual(wiz.state, "preview")
        self.assertEqual(self.Reg.search_count([]), before)
        move.invalidate_recordset()
        self.assertFalse(move.justech_do_fiscal_regularization_id)

    def test_execute_creates_missing_and_second_run_zero(self):
        move = self._voided_move(
            name_ncf="B0100004102",
            invoice_day=date(2026, 4, 15),
            void_day=date(2026, 7, 20),
            cancel_type="04",
        )
        wiz = self.Wiz.create({"company_id": self.company.id})
        wiz.action_preview()
        line = wiz.line_ids.filtered(lambda l: l.move_id == move)
        self.assertTrue(line)
        self.assertEqual(line.original_fiscal_period, "202604")
        self.assertEqual(line.reporting_period_608, "202604")
        self.assertIn(line.proposed_action, ("create", "create_review"))
        # Solo la línea bajo prueba (LAB puede tener otros anulados históricos)
        wiz.line_ids.write({"selected": False})
        line.write({"selected": True})
        before = self.Reg.search_count([("move_id", "=", move.id)])
        wiz.action_execute()
        self.assertEqual(wiz.count_created, 1)
        self.assertEqual(
            self.Reg.search_count([("move_id", "=", move.id)]), before + 1
        )
        reg = self.Reg.search([("move_id", "=", move.id)], limit=1)
        self.assertEqual(reg.original_fiscal_period, "202604")
        self.assertEqual(reg.source_operation, "historical_backfill")
        self.assertEqual(reg.status_608, "pending")
        self.assertNotEqual(reg.status_608, "presented")
        # segunda ejecución: ese move ya no es elegible
        wiz2 = self.Wiz.create({"company_id": self.company.id})
        wiz2.action_preview()
        line2 = wiz2.line_ids.filtered(lambda l: l.move_id == move)
        self.assertEqual(line2.proposed_action, "skip_exists")
        wiz2.line_ids.write({"selected": False})
        before_all = self.Reg.search_count([])
        wiz2.action_execute()
        self.assertEqual(wiz2.count_created, 0)
        self.assertEqual(self.Reg.search_count([]), before_all)
        self.assertEqual(self.Reg.search_count([("move_id", "=", move.id)]), 1)

    def test_april_voided_july_period_april(self):
        move = self._voided_move(
            name_ncf="B0100004103",
            invoice_day=date(2026, 4, 13),
            void_day=date(2026, 7, 27),
        )
        reg = self.Svc.create_historical_regularization(move)
        self.assertEqual(reg.original_fiscal_period, "202604")
        exporter = self.env["justech.do.dgii.608.exporter"]
        self.assertTrue(
            exporter._move_in_608_period(move, date(2026, 4, 1), date(2026, 4, 30))
        )
        self.assertFalse(
            exporter._move_in_608_period(move, date(2026, 7, 1), date(2026, 7, 31))
        )

    def test_july_voided_july_period_july(self):
        move = self._voided_move(
            name_ncf="B0100004104",
            invoice_day=date(2026, 7, 10),
            void_day=date(2026, 7, 28),
        )
        reg = self.Svc.create_historical_regularization(move)
        self.assertEqual(reg.original_fiscal_period, "202607")

    def test_active_ncf_not_in_preview(self):
        partner = self.env["res.partner"].create({"name": "Active"})
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": date(2026, 7, 1),
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 10})
                ],
            }
        )
        move.write({"justech_do_ncf": "B0100004105", "justech_do_ncf_voided": False})
        wiz = self.Wiz.create({"company_id": self.company.id})
        wiz.action_preview()
        self.assertFalse(wiz.line_ids.filtered(lambda l: l.move_id == move))

    def test_no_ncf_not_in_preview(self):
        partner = self.env["res.partner"].create({"name": "NoNCF"})
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": date(2026, 7, 1),
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 10})
                ],
            }
        )
        move.write(
            {
                "justech_do_ncf_voided": True,
                "state": "cancel",
                "justech_do_dgii_fiscal_state": "cancelled",
            }
        )
        wiz = self.Wiz.create({"company_id": self.company.id})
        wiz.action_preview()
        self.assertFalse(wiz.line_ids.filtered(lambda l: l.move_id == move))

    def test_unknown_motivo_create_review(self):
        move = self._voided_move(
            name_ncf="B0100004106",
            invoice_day=date(2026, 7, 5),
            cancel_type=False,
        )
        move.write({"justech_do_ncf_cancel_type": False})
        wiz = self.Wiz.create({"company_id": self.company.id})
        wiz.action_preview()
        line = wiz.line_ids.filtered(lambda l: l.move_id == move)
        self.assertEqual(line.proposed_action, "create_review")
        wiz.action_execute()
        reg = self.Reg.search([("move_id", "=", move.id)], limit=1)
        self.assertEqual(reg.general_status, "review_required")
        self.assertFalse(reg.annulment_type_608)

    def test_activity_not_duplicated(self):
        move = self._voided_move(
            name_ncf="B0100004107",
            invoice_day=date(2026, 7, 8),
        )
        reg1 = self.Svc.create_historical_regularization(move)
        acts1 = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "justech.do.fiscal.regularization"),
                ("res_id", "=", reg1.id),
            ]
        )
        reg2 = self.Svc.create_historical_regularization(move)
        self.assertEqual(reg1, reg2)
        acts2 = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "justech.do.fiscal.regularization"),
                ("res_id", "=", reg1.id),
            ]
        )
        self.assertEqual(acts1, acts2)

    def test_dashboard_open_no_writes(self):
        move = self._voided_move(
            name_ncf="B0100004108",
            invoice_day=date(2026, 7, 9),
        )
        before = self.Reg.search_count([])
        dash = self.env["justech.do.fiscal.dashboard"].create(
            {"company_id": self.company.id}
        )
        dash.action_refresh()
        self.assertEqual(self.Reg.search_count([]), before)
        self.assertFalse(move.justech_do_fiscal_regularization_id)

    def test_608_preview_includes_after_backfill(self):
        move = self._voided_move(
            name_ncf="B0100004109",
            invoice_day=date(2026, 7, 12),
            cancel_type="04",
        )
        self.Svc.create_historical_regularization(move)
        exporter = self.env["justech.do.dgii.608.exporter"]
        buckets = exporter.classify_moves(
            self.company,
            date(2026, 7, 1),
            date(2026, 7, 31),
            refresh_states=False,
        )
        self.assertIn(move, buckets["all"])
