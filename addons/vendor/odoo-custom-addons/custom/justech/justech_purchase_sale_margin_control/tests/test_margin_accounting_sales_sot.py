# -*- coding: utf-8 -*-
"""19.0.8.23.0 — Dashboard Ventas reales from posted account.move (not MTX)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginAccountingSalesSoT(TransactionCase):
    """KPI Ventas = accounting SoT (amount_untaxed_signed), independent of MTX."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Board = cls.env["purchase.sale.margin.board"]
        cls.Move = cls.env["account.move"]

    def _posted_signed_sum(self, company, date_from, date_to):
        self.env.cr.execute(
            """
            SELECT COALESCE(SUM(amount_untaxed_signed), 0)
            FROM account_move
            WHERE company_id = %s
              AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND invoice_date >= %s
              AND invoice_date <= %s
            """,
            (company.id, date_from, date_to),
        )
        return float(self.env.cr.fetchone()[0] or 0.0)

    def _posted_counts(self, company, date_from, date_to):
        self.env.cr.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE move_type = 'out_invoice'),
              COUNT(*) FILTER (WHERE move_type = 'out_refund')
            FROM account_move
            WHERE company_id = %s
              AND state = 'posted'
              AND move_type IN ('out_invoice', 'out_refund')
              AND invoice_date >= %s
              AND invoice_date <= %s
            """,
            (company.id, date_from, date_to),
        )
        inv, nc = self.env.cr.fetchone()
        return int(inv or 0), int(nc or 0)

    def test_dashboard_sales_match_posted_accounting_signed(self):
        date_from, date_to = "2026-01-01", "2026-12-31"
        kpis = self.Board._compute_kpis(self.company, date_from, date_to)
        expected = self._posted_signed_sum(self.company, date_from, date_to)
        inv_n, nc_n = self._posted_counts(self.company, date_from, date_to)
        self.assertAlmostEqual(kpis["total_sales_amount"], expected, places=2)
        self.assertEqual(kpis["total_sales_count"], inv_n)
        self.assertEqual(kpis["posted_credit_note_count"], nc_n)
        # Must not fall back to MTX sale_real_amount as primary source.
        self.assertIn("estimated_sales_amount", kpis)
        self.assertIn("margin_ops_count", kpis)

    def test_cross_company_isolation(self):
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) < 2:
            self.skipTest("Need at least 2 companies")
        co_a, co_b = companies[0], companies[1]
        moves_a = self.Board._accounting_sales_moves(co_a, "2026-01-01", "2026-12-31")
        moves_b = self.Board._accounting_sales_moves(co_b, "2026-01-01", "2026-12-31")
        self.assertTrue(all(m.company_id == co_a for m in moves_a))
        self.assertTrue(all(m.company_id == co_b for m in moves_b))
        self.assertFalse(set(moves_a.ids) & set(moves_b.ids))
        cross = sum(1 for m in moves_a if m.company_id != co_a)
        self.assertEqual(cross, 0)

    def test_invoice_without_mtx_still_in_sales_kpi(self):
        """If a posted invoice exists without MTX, it still contributes to Ventas reales."""
        date_from, date_to = "2026-01-01", "2026-12-31"
        moves = self.Board._accounting_sales_moves(self.company, date_from, date_to)
        invoices = moves.filtered(lambda m: m.move_type == "out_invoice")
        if not invoices:
            self.skipTest("No posted customer invoices in period")
        linked = self.Board._mtx_linked_customer_invoice_ids(self.company)
        unlinked = invoices.filtered(lambda m: m.id not in linked)
        kpis = self.Board._compute_kpis(self.company, date_from, date_to)
        self.assertAlmostEqual(
            kpis["total_sales_amount"],
            sum(moves.mapped("amount_untaxed_signed")),
            places=2,
        )
        if unlinked:
            # Unlinked posted sales are included in SWC operational bucket.
            self.assertGreaterEqual(
                kpis["sales_without_cost_amount"],
                min(unlinked.mapped("amount_untaxed_signed")),
            )

    def test_action_open_all_sales_uses_account_move(self):
        board = self.Board.create(
            {
                "company_id": self.company.id,
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
            }
        )
        action = board.action_open_all_sales()
        self.assertEqual(action["res_model"], "account.move")
        self.assertIn(("state", "=", "posted"), action["domain"])
        self.assertIn(("move_type", "in", ("out_invoice", "out_refund")), action["domain"])
