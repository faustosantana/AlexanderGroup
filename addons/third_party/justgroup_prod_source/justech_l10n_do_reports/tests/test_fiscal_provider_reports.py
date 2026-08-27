"""Tests reportes DGII leyendo NCF vía Fiscal Data Provider (Adel/latam)."""
from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestFiscalProviderReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.exporter_606 = cls.env["justech.do.dgii.606.exporter"]
        cls.exporter_607 = cls.env["justech.do.dgii.607.exporter"]
        cls.Move = cls.env["account.move"]
        cls.has_latam = "l10n_latam_document_number" in cls.Move._fields

    def _vendor(self, vat="131793916"):
        return self.env["res.partner"].create(
            {"name": "Proveedor Adel compat", "vat": vat, "supplier_rank": 1}
        )

    def _customer(self, vat="131793916"):
        return self.env["res.partner"].create(
            {"name": "Cliente Adel compat", "vat": vat, "customer_rank": 1}
        )

    def test_606_validates_adel_ncf_without_justech_field(self):
        if not self.has_latam:
            self.skipTest("l10n_latam_document_number not available")
        partner = self._vendor()
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        tax = self.env["account.tax"].search(
            [
                ("company_id", "=", self.company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", ">", 0),
            ],
            limit=1,
        )
        product = self.env["product.product"].create(
            {
                "name": "Producto Adel 606",
                "type": "consu",
                "is_storable": True,
                "standard_price": 100.0,
                "supplier_taxes_id": [Command.set(tax.ids)],
            }
        )
        move = self.Move.create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": date.today(),
                "l10n_latam_document_number": "B1100000999",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        move.action_post()
        date_from = date.today().replace(day=1)
        date_to = date.today()
        errors = self.exporter_606._dgii_validate_single_move(move, date_from, date_to)
        ncf_errors = [e for e in errors if "no tiene NCF" in e]
        self.assertEqual(ncf_errors, [], errors)
        row = self.exporter_606._dgii_build_row_values(move, 1, date_from, date_to)
        self.assertEqual(row["E"], "B1100000999")

    def test_607_ecf_invoice_e310000019120(self):
        if not self.has_latam:
            self.skipTest("l10n_latam_document_number not available")
        partner = self._customer()
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        tax = self.env["account.tax"].search(
            [
                ("company_id", "=", self.company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", ">", 0),
            ],
            limit=1,
        )
        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": date.today(),
                "l10n_latam_document_number": "E310000019120",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Línea e-CF",
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        date_from = date.today().replace(day=1)
        date_to = date.today()
        errors = self.exporter_607._dgii_validate_single_move(move, date_from, date_to)
        ncf_errors = [e for e in errors if "no tiene NCF" in e]
        self.assertEqual(ncf_errors, [], errors)
        row = self.exporter_607._dgii_build_row_values(move, 1, date_from, date_to)
        self.assertEqual(row["D"], "E310000019120")
