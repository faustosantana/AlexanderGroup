# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.1 — display SoT + friendly IntegrityError."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_ncf_hotfix_202611")
class TestNcfHotfix202611(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.company.justech_do_fiscal_enabled = True
        cls.FiscalError = cls.env["justech.do.fiscal.error.service"]
        cls.FDP = cls.env["justech.do.fiscal.data.provider"]
        cls.Move = cls.env["account.move"]

    def test_fdp_prefers_justech_when_latam_empty(self):
        """List/form SoT: Justech NCF visible even if LATAM empty (dual-write OFF)."""
        move = self.Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "justech_do_ncf": "B0100000348",
                "l10n_latam_document_number": False,
            }
        )
        self.assertEqual(self.FDP.get_ncf(move), "B0100000348")

    def test_integrity_sale_uniq_maps_to_user_error(self):
        class FakeExc(Exception):
            pass

        exc = FakeExc(
            'duplicate key value violates unique constraint '
            '"account_move_justech_do_ncf_sale_uniq" DETAIL: Key (B0100000345)'
        )
        msg = self.FiscalError.map_exception(exc, company=self.company, ncf="B0100000345")
        self.assertTrue(msg)
        self.assertNotIn("duplicate key", msg.lower())
        self.assertNotIn("violates unique", msg.lower())
        self.assertIn("B0100000345", msg)
        self.assertIn("comprobante fiscal", msg.lower())

    def test_reraise_non_fiscal_passthrough(self):
        with self.assertRaises(RuntimeError):
            self.FiscalError.reraise_as_user_error(RuntimeError("unrelated"))

    def test_reraise_fiscal_raises_user_error(self):
        exc = Exception(
            'duplicate key value violates unique constraint '
            "account_move_justech_do_ncf_sale_uniq"
        )
        with self.assertRaises(UserError) as ctx:
            self.FiscalError.reraise_as_user_error(
                exc, company=self.company, ncf="B0100000999"
            )
        self.assertNotIn("duplicate key", str(ctx.exception).lower())
