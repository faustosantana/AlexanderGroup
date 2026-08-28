# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.5 — PDF invoice NCF with dual-write OFF (read-only SoT)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_hotfix_202615")
class TestInvoicePdfNcfSot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Move = cls.env["account.move"]
        cls.Report = cls.env["ir.actions.report"]

    def _html(self, move):
        html = self.Report._render_qweb_html("account.account_invoices", move.ids)[0]
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        return html

    def test_justech_get_ncf_prefers_justech_when_latam_empty(self):
        move = self.Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.env.company.id,
                "justech_do_ncf": "B0100000999",
                "l10n_latam_document_number": False,
            }
        )
        self.assertEqual(move.justech_get_ncf(), "B0100000999")

    def test_pdf_shows_ncf_when_latam_empty_if_posted_sample_exists(self):
        """Regression: dual-write OFF invoices must print Justech NCF in #do_informations."""
        move = self.Move.search(
            [
                ("state", "=", "posted"),
                ("move_type", "=", "out_invoice"),
                ("justech_do_ncf", "!=", False),
                ("l10n_latam_document_number", "in", [False, ""]),
            ],
            limit=1,
        )
        if not move:
            self.skipTest("No posted invoice with Justech NCF and empty LATAM")
        html = self._html(move)
        self.assertIn(move.justech_do_ncf, html)
        # Must appear in visible DO fiscal block, not only hidden #informations
        do_idx = html.find('id="do_informations"')
        info_idx = html.find('id="informations"')
        self.assertGreaterEqual(do_idx, 0)
        ncf_in_do = html.find(move.justech_do_ncf, do_idx, info_idx if info_idx > do_idx else None)
        self.assertGreaterEqual(ncf_in_do, 0, "NCF must render inside #do_informations")
