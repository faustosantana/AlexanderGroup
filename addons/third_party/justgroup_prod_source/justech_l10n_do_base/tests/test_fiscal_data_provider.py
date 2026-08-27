"""Tests Fiscal Data Provider — coexistencia Justech / Adel / l10n_latam."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestFiscalDataProvider(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["justech.do.fiscal.data.provider"]
        cls.Move = cls.env["account.move"]

    def test_get_ncf_from_justech_field(self):
        move = self.Move.new({"justech_do_ncf": "B0100000123"})
        self.assertEqual(self.provider.get_ncf(move), "B0100000123")

    def test_get_ncf_from_latam_field_when_justech_empty(self):
        if "l10n_latam_document_number" not in self.Move._fields:
            self.skipTest("l10n_latam_document_number not installed")
        move = self.Move.new(
            {
                "justech_do_ncf": False,
                "l10n_latam_document_number": "E310000019120",
            }
        )
        self.assertEqual(self.provider.get_ncf(move), "E310000019120")
        self.assertEqual(self.provider.get_supported_sources(move), "adel_latam")

    def test_justech_takes_priority_over_latam(self):
        if "l10n_latam_document_number" not in self.Move._fields:
            self.skipTest("l10n_latam_document_number not installed")
        move = self.Move.new(
            {
                "justech_do_ncf": "B0200000001",
                "l10n_latam_document_number": "E310000019120",
            }
        )
        self.assertEqual(self.provider.get_ncf(move), "B0200000001")
        self.assertEqual(self.provider.get_supported_sources(move), "justech")

    def test_document_type_prefix_from_ncf(self):
        move = self.Move.new({"l10n_latam_document_number": "E310000019120"})
        self.assertEqual(self.provider.get_document_type_prefix(move), "E31")
        self.assertTrue(self.provider.is_ecf(move))

    def test_income_type_from_latam_field(self):
        if "l10n_do_income_type" not in self.Move._fields:
            self.skipTest("l10n_do_income_type not installed")
        move = self.Move.new({"l10n_do_income_type": "02"})
        self.assertEqual(self.provider.get_income_type_607(move), "02")

    def test_expense_type_from_latam_field(self):
        if "l10n_do_expense_type" not in self.Move._fields:
            self.skipTest("l10n_do_expense_type not installed")
        move = self.Move.new({"l10n_do_expense_type": "06"})
        self.assertEqual(self.provider.get_expense_type_606(move), "06")

    def test_cancellation_type_from_latam(self):
        if "l10n_do_cancellation_type" not in self.Move._fields:
            self.skipTest("l10n_do_cancellation_type not installed")
        move = self.Move.new({"l10n_do_cancellation_type": "04"})
        self.assertEqual(self.provider.get_cancellation_type(move), "4")
        self.assertTrue(self.provider.is_voided(move))

    def test_get_ncf_returns_empty_when_missing(self):
        move = self.Move.new({"name": "INV/2026/0001", "ref": "PO-123"})
        self.assertEqual(self.provider.get_ncf(move), "")
        self.assertEqual(self.provider.get_supported_sources(move), "none")

    def test_get_ncf_accepts_vendor_ecf_14_chars(self):
        """Omega-style e-NCF (E31 + 11 sequence digits) must display after post."""
        if "l10n_latam_document_number" not in self.Move._fields:
            self.skipTest("l10n_latam_document_number not installed")
        move = self.Move.new(
            {
                "justech_do_ncf": False,
                "l10n_latam_document_number": "E3100000106285",
            }
        )
        self.assertEqual(self.provider.get_ncf(move), "E3100000106285")
        self.assertEqual(self.provider.get_document_type_prefix(move), "E31")
        self.assertEqual(self.provider.get_supported_sources(move), "adel_latam")
