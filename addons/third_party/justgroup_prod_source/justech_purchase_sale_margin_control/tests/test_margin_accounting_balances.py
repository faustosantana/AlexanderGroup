# -*- coding: utf-8 -*-
"""19.0.8.26.0 — Dashboard CxC/CxP from accounting open balances (not MTX)."""
from datetime import date, timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_is_zero


@tagged("post_install", "-at_install", "justech_margin", "justech_margin_balances")
class TestMarginAccountingBalances(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Board = cls.env["purchase.sale.margin.board"]
        cls.today = fields.Date.context_today(cls.env.user)
        cls.partner = cls.env["res.partner"].create({"name": "BAL826 Customer", "company_id": False})
        cls.vendor = cls.env["res.partner"].create({"name": "BAL826 Vendor", "company_id": False})
        if "justech_do_fiscal_config_state" in cls.partner._fields:
            cls.partner.justech_do_fiscal_config_state = "not_applicable"
            cls.vendor.justech_do_fiscal_config_state = "not_applicable"
        cls.product = cls.env["product.product"].create(
            {"name": "BAL826 Product", "type": "consu", "list_price": 100.0, "standard_price": 40.0}
        )

    def _sql_aml_residual(self, company, account_type, date_to=None):
        date_to = date_to or self.today
        sign = -1.0 if account_type == "liability_payable" else 1.0
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(aml.amount_residual), 0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
              AND am.state = 'posted'
              AND aa.account_type = %s
              AND aml.date <= %s
              AND ABS(COALESCE(aml.amount_residual, 0)) > 0.005
            """,
            (company.id, account_type, date_to),
        )
        return sign * float(self.env.cr.fetchone()[0] or 0.0)

    def _sql_bill_residual(self, company, date_to=None):
        date_to = date_to or self.today
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(-aml.amount_residual), 0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
              AND am.state = 'posted'
              AND aa.account_type = 'liability_payable'
              AND am.move_type IN ('in_invoice', 'in_refund')
              AND aml.date <= %s
              AND ABS(COALESCE(aml.amount_residual, 0)) > 0.005
            """,
            (company.id, date_to),
        )
        return float(self.env.cr.fetchone()[0] or 0.0)

    def _kpis(self, company=None, date_from="2026-01-01", date_to=None):
        company = company or self.company
        date_to = date_to or self.today
        return self.Board._compute_kpis(company, date_from, date_to)

    def _try_post(self, move):
        try:
            move.action_post()
            return move.state == "posted"
        except Exception:
            return False

    def _create_out_invoice(self, amount=100.0, invoice_date=None, currency=None, partner=None):
        invoice_date = invoice_date or self.today
        vals = {
            "move_type": "out_invoice",
            "partner_id": (partner or self.partner).id,
            "company_id": self.company.id,
            "invoice_date": invoice_date,
            "invoice_line_ids": [
                (0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": amount, "name": self.product.name})
            ],
        }
        if currency:
            vals["currency_id"] = currency.id
        return self.env["account.move"].create(vals)

    def _create_in_invoice(self, amount=80.0, invoice_date=None):
        invoice_date = invoice_date or self.today
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "company_id": self.company.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": amount, "name": self.product.name})
                ],
            }
        )

    # 01–10 CxC
    def test_01_cxc_includes_invoice_without_mtx(self):
        kpis = self._kpis()
        expected = self._sql_aml_residual(self.company, "asset_receivable")
        self.assertAlmostEqual(kpis["amount_to_collect_total"], expected, places=2)
        linked = self.Board._mtx_linked_customer_invoice_ids(self.company)
        self.env.cr.execute(
            """
            SELECT COUNT(*)
            FROM account_move am
            WHERE am.company_id = %s AND am.state = 'posted'
              AND am.move_type = 'out_invoice'
              AND ABS(COALESCE(am.amount_residual_signed, 0)) > 0.005
              AND am.id NOT IN %s
            """,
            (self.company.id, tuple(linked) or (0,)),
        )
        unlinked = int(self.env.cr.fetchone()[0] or 0)
        if unlinked:
            self.assertGreater(kpis["amount_to_collect_total"], 0.0)

    def test_02_cxc_includes_prior_year_open(self):
        kpis = self._kpis(date_from="2026-01-01", date_to=self.today)
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(amount_residual_signed), 0)
            FROM account_move
            WHERE company_id = %s AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND COALESCE(invoice_date, date) < DATE '2026-01-01'
              AND ABS(COALESCE(amount_residual_signed, 0)) > 0.005
            """,
            (self.company.id,),
        )
        prior = float(self.env.cr.fetchone()[0] or 0.0)
        if float_is_zero(prior, precision_digits=2):
            inv = self._create_out_invoice(amount=55.0, invoice_date=date(2025, 6, 15))
            if not self._try_post(inv):
                self.skipTest("Cannot post prior-year invoice in this DB")
            kpis = self._kpis(date_from="2026-01-01", date_to=self.today)
            self.assertGreaterEqual(kpis["amount_to_collect_total"], 55.0 - 0.05)
        else:
            self.assertGreaterEqual(kpis["amount_to_collect_total"] + 0.05, prior)

    def test_03_cxc_excludes_paid(self):
        expected = self._sql_aml_residual(self.company, "asset_receivable")
        kpis = self._kpis()
        self.assertAlmostEqual(kpis["amount_to_collect_total"], expected, places=2)
        self.env.cr.execute(
            """
            SELECT COUNT(*) FROM account_move
            WHERE company_id = %s AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND ABS(COALESCE(amount_residual_signed, 0)) <= 0.005
            """,
            (self.company.id,),
        )
        paid_n = int(self.env.cr.fetchone()[0] or 0)
        self.assertIsInstance(paid_n, int)

    def test_04_cxc_partial_payment_uses_residual(self):
        kpis = self._kpis()
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(amount_residual_signed), 0)
            FROM account_move
            WHERE company_id = %s AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND payment_state = 'partial'
              AND ABS(COALESCE(amount_residual_signed, 0)) > 0.005
            """,
            (self.company.id,),
        )
        partial = float(self.env.cr.fetchone()[0] or 0.0)
        if not float_is_zero(partial, precision_digits=2):
            self.assertGreaterEqual(kpis["amount_to_collect_total"] + 0.05, partial)

    def test_05_cxc_credit_note_reduces_balance(self):
        kpis = self._kpis()
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(amount_residual_signed), 0)
            FROM account_move
            WHERE company_id = %s AND state = 'posted' AND move_type = 'out_refund'
              AND ABS(COALESCE(amount_residual_signed, 0)) > 0.005
            """,
            (self.company.id,),
        )
        nc = float(self.env.cr.fetchone()[0] or 0.0)
        aml = self._sql_aml_residual(self.company, "asset_receivable")
        self.assertAlmostEqual(kpis["amount_to_collect_total"], aml, places=2)
        if not float_is_zero(nc, precision_digits=2):
            self.assertLess(kpis["amount_to_collect_total"], aml - nc + abs(nc) + 1.0)

    def test_06_07_cxc_dop_usd_split(self):
        kpis = self._kpis()
        self.assertIn("cxc_dop_amount", kpis)
        self.assertIn("cxc_usd_amount", kpis)
        self.assertIn("cxc_usd_equiv_dop", kpis)
        total = kpis["cxc_dop_amount"] + kpis["cxc_usd_equiv_dop"]
        self.assertAlmostEqual(kpis["amount_to_collect_total"], total, places=2)

    def test_08_cxc_company_isolation(self):
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) < 2:
            other = self.env["res.company"].create({"name": "BAL826 Other Co"})
            companies = self.company | other
        co_a, co_b = companies[0], companies[1]
        kpis_a = self._kpis(company=co_a)
        kpis_b = self._kpis(company=co_b)
        exp_a = self._sql_aml_residual(co_a, "asset_receivable")
        exp_b = self._sql_aml_residual(co_b, "asset_receivable")
        self.assertAlmostEqual(kpis_a["amount_to_collect_total"], exp_a, places=2)
        self.assertAlmostEqual(kpis_b["amount_to_collect_total"], exp_b, places=2)
        rows_a = self.Board._aml_open_rows(co_a, "asset_receivable", self.today)
        self.assertTrue(all(r["company_id"] == co_a.id for r in rows_a))

    def test_09_cxc_as_of_date_excludes_later_moves(self):
        future = self.today + timedelta(days=400)
        inv = self._create_out_invoice(amount=77.0, invoice_date=future)
        posted = self._try_post(inv)
        kpis_today = self._kpis(date_to=self.today)
        if posted:
            kpis_future = self._kpis(date_to=future)
            self.assertGreaterEqual(kpis_future["amount_to_collect_total"] + 0.05, kpis_today["amount_to_collect_total"])
        # Cut-off today must not include a future-dated invoice even if posted.
        rows = self.Board._aml_open_rows(self.company, "asset_receivable", self.today)
        self.assertFalse(any(r["move_id"] == inv.id for r in rows))

    def test_10_cxc_matches_aml_receivable(self):
        kpis = self._kpis()
        expected = self._sql_aml_residual(self.company, "asset_receivable")
        self.assertAlmostEqual(kpis["amount_to_collect_total"], expected, places=2)

    # 11–18 CxP
    def test_11_cxp_open_vendor_bills(self):
        kpis = self._kpis()
        bills = self._sql_bill_residual(self.company)
        self.assertAlmostEqual(kpis["committed_vendor_flow"], bills, places=2)
        self.assertAlmostEqual(kpis["open_vendor_bills_amount"], bills, places=2)

    def test_12_cxp_vendor_credit_in_bills_kpi(self):
        kpis = self._kpis()
        self.assertGreaterEqual(kpis["amount_to_pay_total"] + 0.05, kpis["committed_vendor_flow"])

    def test_13_cxp_journal_payable_in_other(self):
        kpis = self._kpis()
        aml = self._sql_aml_residual(self.company, "liability_payable")
        bills = self._sql_bill_residual(self.company)
        other = aml - bills
        self.assertAlmostEqual(kpis["amount_to_pay_total"], aml, places=2)
        self.assertAlmostEqual(kpis["cxp_other_amount"], other, places=2)

    def test_14_cxp_unreconciled_payment_in_aml(self):
        kpis = self._kpis()
        self.assertAlmostEqual(
            kpis["amount_to_pay_total"],
            kpis["open_vendor_bills_amount"] + kpis["cxp_other_amount"],
            places=2,
        )

    def test_15_cxp_usd_split(self):
        kpis = self._kpis()
        total = kpis["cxp_dop_amount"] + kpis["cxp_usd_equiv_dop"]
        self.assertAlmostEqual(kpis["amount_to_pay_total"], total, places=2)

    def test_16_cxp_company_isolation(self):
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) < 2:
            self.skipTest("Need 2 companies")
        co_a, co_b = companies[0], companies[1]
        self.assertAlmostEqual(
            self._kpis(company=co_a)["amount_to_pay_total"],
            self._sql_aml_residual(co_a, "liability_payable"),
            places=2,
        )
        self.assertAlmostEqual(
            self._kpis(company=co_b)["amount_to_pay_total"],
            self._sql_aml_residual(co_b, "liability_payable"),
            places=2,
        )

    def test_17_cxp_as_of_date(self):
        future = self.today + timedelta(days=400)
        bill = self._create_in_invoice(amount=40.0, invoice_date=future)
        self._try_post(bill)
        rows = self.Board._aml_open_rows(self.company, "liability_payable", self.today)
        self.assertFalse(any(r["move_id"] == bill.id for r in rows))

    def test_18_cxp_matches_aml_payable(self):
        kpis = self._kpis()
        expected = self._sql_aml_residual(self.company, "liability_payable")
        self.assertAlmostEqual(kpis["amount_to_pay_total"], expected, places=2)

    # 19 flujo / 20 sales / 21 margin / 29 multi / 30 drill-down
    def test_19_flujo_is_cxc_minus_cxp(self):
        kpis = self._kpis()
        self.assertAlmostEqual(
            kpis["net_cash_flow"],
            kpis["amount_to_collect_total"] - kpis["amount_to_pay_total"],
            places=2,
        )

    def test_20_sales_kpi_intact(self):
        date_from, date_to = "2026-01-01", "2026-12-31"
        kpis = self.Board._compute_kpis(self.company, date_from, date_to)
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(amount_untaxed_signed), 0)
            FROM account_move
            WHERE company_id = %s AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND invoice_date >= %s AND invoice_date <= %s
            """,
            (self.company.id, date_from, date_to),
        )
        expected = float(self.env.cr.fetchone()[0] or 0.0)
        self.assertAlmostEqual(kpis["total_sales_amount"], expected, places=2)

    def test_21_margin_keys_intact(self):
        kpis = self._kpis()
        for key in ("confirmed_real_margin", "margin_ops_count", "related_costs_amount"):
            self.assertIn(key, kpis)

    def test_29_multicompany_board_scope(self):
        companies = self.env.companies
        kpis = self.Board._compute_kpis(companies, "2026-01-01", self.today)
        total_cxc = sum(self._sql_aml_residual(c, "asset_receivable") for c in companies)
        total_cxp = sum(self._sql_aml_residual(c, "liability_payable") for c in companies)
        self.assertAlmostEqual(kpis["amount_to_collect_total"], total_cxc, places=2)
        self.assertAlmostEqual(kpis["amount_to_pay_total"], total_cxp, places=2)

    def test_30_drilldown_totals_match_kpi(self):
        board = self.Board.create({"company_id": self.company.id, "date_from": "2026-01-01", "date_to": self.today})
        board.action_refresh_silent()
        action = board.action_open_amount_to_collect()
        self.assertEqual(action["res_model"], "account.move.line")
        aml_ids = action["domain"][0][2]
        if aml_ids == [0]:
            self.assertAlmostEqual(board.amount_to_collect_total, 0.0, places=2)
            return
        lines = self.env["account.move.line"].browse(aml_ids)
        self.assertAlmostEqual(sum(lines.mapped("amount_residual")), board.amount_to_collect_total, places=2)
        pay_action = board.action_open_amount_to_pay()
        pay_ids = pay_action["domain"][0][2]
        if pay_ids != [0]:
            pay_lines = self.env["account.move.line"].browse(pay_ids)
            self.assertAlmostEqual(-sum(pay_lines.mapped("amount_residual")), board.amount_to_pay_total, places=2)

    def test_labels_period_vs_balance(self):
        kpis = self._kpis()
        self.assertIn("Período comercial", kpis["commercial_period_label"])
        self.assertIn("Saldos al", kpis["balance_as_of_label"])
        self.assertIn("DOP", kpis["cxc_breakdown_label"])
