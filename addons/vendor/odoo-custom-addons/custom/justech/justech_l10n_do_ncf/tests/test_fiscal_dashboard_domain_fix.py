# -*- coding: utf-8 -*-
"""Hotfix dominio dashboard + refresh sin RPC_ERROR."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_fiscal_dashboard")
class TestFiscalDashboardDomainFix(TransactionCase):
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
                "name": "Dash Domain Resp",
                "login": "dash.domain.%s" % id(cls),
                "email": "dash.domain@example.com",
            }
        )
        cls.company.justech_do_fiscal_regularization_user_id = cls.responsible.id

    def _make_reg(self, period, ncf):
        partner = self.env["res.partner"].create({"name": "P %s" % ncf})
        inv_day = date(int(period[:4]), int(period[4:6]), 10)
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": inv_day,
                "invoice_line_ids": [
                    (0, 0, {"name": "L", "quantity": 1, "price_unit": 10})
                ],
            }
        )
        move.write(
            {
                "justech_do_ncf": ncf,
                "justech_do_ncf_voided": True,
                "state": "cancel",
                "justech_do_original_fiscal_period": period,
                "justech_do_608_reporting_period": period,
            }
        )
        return self.Reg.create(
            {
                "company_id": self.company.id,
                "move_id": move.id,
                "ncf": ncf,
                "original_fiscal_period": period,
                "reporting_period_608": period,
                "required_608": True,
                "status_608": "pending",
                "responsible_user_id": self.responsible.id,
                "source_operation": "manual",
            }
        )

    def test_reg_base_domain_single_company(self):
        self._make_reg("202607", "B0100003101")
        dash = self.Dash.create(
            {
                "company_id": self.company.id,
                "filter_all_allowed_companies": False,
            }
        )
        domain = dash._reg_base_domain()
        self.assertIn(("company_id", "=", self.company.id), domain)
        # Must be list of domain leaves/operators — no naked strings as append args
        for leaf in domain:
            self.assertTrue(
                isinstance(leaf, (tuple, list, str)),
                "invalid domain leaf %r" % (leaf,),
            )
            if isinstance(leaf, str):
                self.assertIn(leaf, ("|", "&", "!"))

    def test_reg_base_domain_with_period_uses_extend_or(self):
        dash = self.Dash.create(
            {
                "company_id": self.company.id,
                "filter_period": "202607",
            }
        )
        domain = dash._reg_base_domain()
        self.assertIn("|", domain)
        self.assertIn(("original_fiscal_period", "=", "202607"), domain)
        self.assertIn(("reporting_period_608", "=", "202607"), domain)
        # append("|", a, b) would have raised; building domain must succeed
        self.Reg.search(domain)

    def test_reg_base_domain_multi_company_flag(self):
        dash = self.Dash.create(
            {
                "company_id": self.company.id,
                "filter_all_allowed_companies": True,
            }
        )
        domain = dash._reg_base_domain()
        self.assertTrue(
            any(
                isinstance(leaf, (list, tuple))
                and len(leaf) == 3
                and leaf[0] == "company_id"
                and leaf[1] == "in"
                for leaf in domain
            )
        )

    def test_refresh_with_period_and_responsible_no_error(self):
        self._make_reg("202607", "B0100003102")
        self._make_reg("202604", "B0100003103")
        dash = self.Dash.create(
            {
                "company_id": self.company.id,
                "filter_period": "202607",
                "filter_responsible_id": self.responsible.id,
            }
        )
        dash.action_refresh()
        self.assertTrue(dash.last_refresh)
        codes = set(dash.period_line_ids.mapped("period_code"))
        self.assertEqual(codes, {"202607"})

    def test_refresh_without_period_shows_all_periods(self):
        self._make_reg("202607", "B0100003104")
        self._make_reg("202604", "B0100003105")
        dash = self.Dash.create({"company_id": self.company.id})
        dash.action_refresh()
        codes = set(dash.period_line_ids.mapped("period_code"))
        self.assertIn("202607", codes)
        self.assertIn("202604", codes)

    def test_empty_period_filter_ignored(self):
        dash = self.Dash.create(
            {"company_id": self.company.id, "filter_period": "  "}
        )
        domain = dash._reg_base_domain()
        self.assertNotIn("|", domain)
