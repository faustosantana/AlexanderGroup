# -*- coding: utf-8 -*-
"""Baseline permanente — Alertas NCF internas consolidadas (sin correo).

PROTECTED BASELINE commit: aaea7f5f4730a038f005a3e6010354f9da64963a
Tag: ncf-alerts-baseline-v1
"""
from datetime import date, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_ncf_alerts_baseline")
class TestNcfAlertsConsolidatedBaseline(TransactionCase):
    """Garantiza el comportamiento congelado de alertas NCF."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Range = cls.env["justech.do.ncf.range"]
        cls.Activity = cls.env["mail.activity"]
        cls.Mail = cls.env["mail.mail"]
        cls.SUMMARY = cls.Range.CONSOLIDATED_ALERT_SUMMARY

        # Synthetic companies only — avoid pollution from production ranges on
        # env.company when tests run against a restored DEV/Prod dump.
        do = cls.env.ref("base.do")
        cls.company_a = cls.env["res.company"].create(
            {
                "name": "Baseline NCF Co A",
                "country_id": do.id,
            }
        )
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "Baseline NCF Co B",
                "country_id": do.id,
            }
        )
        for co in (cls.company_a, cls.company_b):
            co.justech_do_fiscal_enabled = True
            co.justech_do_ncf_alert_threshold_critical = 5
            co.justech_do_ncf_alert_threshold_preventive = 20

        manager = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        admin = cls.env.ref("base.user_admin")
        for user in (cls.env.user, admin):
            user.write(
                {
                    "group_ids": [(4, manager.id)],
                    "company_ids": [
                        Command.link(cls.company_a.id),
                        Command.link(cls.company_b.id),
                    ],
                }
            )

        cls.doc_b01 = cls.env.ref("justech_l10n_do_base.doc_type_b01")
        cls.range_a = cls._make_range_cls(cls.company_a, start=1, end=100)
        cls.range_b = cls._make_range_cls(cls.company_b, start=1, end=100)
        cls.range_a.action_activate()
        cls.range_b.action_activate()

    @classmethod
    def _make_range_cls(cls, company, start=1, end=100):
        today = date.today()
        journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
        )
        if not journal:
            journal = cls.env["account.journal"].create(
                {
                    "name": "Sale %s" % company.name,
                    "code": "SN%s" % company.id,
                    "type": "sale",
                    "company_id": company.id,
                }
            )
        return cls.env["justech.do.ncf.range"].create(
            {
                "name": "Baseline B01 %s" % company.id,
                "document_type_id": cls.doc_b01.id,
                "company_id": company.id,
                "sequence_start": start,
                "sequence_end": end,
                "next_sequence": start,
                "date_from": today - timedelta(days=30),
                "date_to": today + timedelta(days=365),
                "journal_ids": [Command.set(journal.ids)],
                "alert_threshold_critical": 5,
                "alert_threshold_preventive": 20,
            }
        )

    def _make_range(self, company, start=1, end=100):
        return self._make_range_cls(company, start=start, end=end)

    def _force_critical(self, rng):
        rng.write({"sequence_end": rng.next_sequence + 4})
        rng._recompute_operational_state()
        return rng

    def _normalize(self, rng):
        rng.write(
            {
                "sequence_end": max(rng.sequence_end, rng.next_sequence + 80),
                "date_to": fields.Date.today() + timedelta(days=200),
            }
        )
        rng._recompute_operational_state()

    def _ncf_mail_count(self):
        return self.Mail.search_count(
            [
                "|",
                "|",
                ("body_html", "ilike", "ALERTA DE RANGOS NCF"),
                ("body_html", "ilike", "Alerta NCF"),
                ("body_html", "ilike", "Revisar rangos NCF"),
            ]
        )

    def _consol_acts(self, company):
        return self.Activity.search(
            [
                ("summary", "=", self.SUMMARY),
                ("res_model", "=", "res.company"),
                ("res_id", "=", company.id),
            ]
        )

    def test_never_creates_mail_mail(self):
        mail0 = self._ncf_mail_count()
        self._force_critical(self.range_a)
        with patch.object(
            type(self.env["mail.mail"]),
            "create",
            side_effect=AssertionError("mail.mail.create no permitido en alertas NCF"),
        ):
            self.Range.with_company(self.company_a)._process_company_consolidated_alert(
                self.company_a
            )
        self.assertEqual(self._ncf_mail_count(), mail0)

    def test_never_sends_smtp(self):
        self._force_critical(self.range_a)
        mail0 = self._ncf_mail_count()
        MailModel = type(self.env["mail.mail"])
        with patch.object(
            MailModel,
            "send",
            side_effect=AssertionError("SMTP send no permitido en alertas NCF"),
        ):
            self.Range.with_company(self.company_a)._process_company_consolidated_alert(
                self.company_a
            )
        self.assertEqual(self._ncf_mail_count(), mail0)

    def test_max_one_activity_per_company(self):
        self._force_critical(self.range_a)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        # Segundo rango crítico misma empresa
        r2 = self._make_range(self.company_a, start=200, end=300)
        r2.action_activate()
        self._force_critical(r2)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        self.assertEqual(len(self._consol_acts(self.company_a)), 1)

    def test_second_run_does_not_duplicate(self):
        self._force_critical(self.range_a)
        res1 = self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        acts1 = self._consol_acts(self.company_a)
        self.assertEqual(len(acts1), 1)
        res2 = self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        acts2 = self._consol_acts(self.company_a)
        self.assertEqual(len(acts2), 1)
        self.assertEqual(acts1.id, acts2.id)
        self.assertEqual(res2.get("activity"), "updated")
        self.assertIn(res1.get("activity"), ("created", "updated"))

    def test_normalize_closes_activity(self):
        self._force_critical(self.range_a)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        self.assertEqual(len(self._consol_acts(self.company_a)), 1)
        self._normalize(self.range_a)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        self.assertEqual(len(self._consol_acts(self.company_a)), 0)

    def test_multicompany_isolation_no_cross_data(self):
        self._force_critical(self.range_a)
        self._force_critical(self.range_b)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        self.Range.with_company(self.company_b)._process_company_consolidated_alert(
            self.company_b
        )
        acts_a = self._consol_acts(self.company_a)
        acts_b = self._consol_acts(self.company_b)
        self.assertEqual(len(acts_a), 1)
        self.assertEqual(len(acts_b), 1)
        self.assertNotEqual(acts_a.id, acts_b.id)
        # Sin cruce: assignee debe tener la empresa en company_ids
        self.assertIn(self.company_a, acts_a.user_id.company_ids)
        self.assertIn(self.company_b, acts_b.user_id.company_ids)
        note_a = acts_a.note or ""
        note_b = acts_b.note or ""
        self.assertIn(self.company_a.display_name, note_a)
        self.assertIn(self.company_b.display_name, note_b)
        self.assertNotIn(self.company_b.display_name, note_a)
        self.assertNotIn(self.company_a.display_name, note_b)

    def test_html_not_raw_escaped(self):
        self._force_critical(self.range_a)
        self.Range.with_company(self.company_a)._process_company_consolidated_alert(
            self.company_a
        )
        act = self._consol_acts(self.company_a)
        self.assertEqual(len(act), 1)
        note = act.note or ""
        self.assertIn("ALERTA DE RANGOS NCF", note)
        self.assertIn("<li>", note)
        self.assertNotIn("&lt;p&gt;", note)
        self.assertNotIn("&lt;li&gt;", note)
        self.assertNotIn("&lt;ul&gt;", note)
        self.assertNotIn("&lt;b&gt;", note)
