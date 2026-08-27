from datetime import date, timedelta

from odoo import Command
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechL10nDoReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.company.justech_do_fiscal_enabled = True
        cls.tax_18 = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("amount", "=", 18),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Report Test Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 50.0,
                "taxes_id": [Command.set(cls.tax_18.ids)],
            }
        )
        cls.journal_sale = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal_sale.justech_do_use_ncf = True
        cls.doc_b02 = cls.env.ref("justech_l10n_do_base.doc_type_b02")
        manager = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        cls.env.user.write({"group_ids": [(4, manager.id)]})
        cls.env["justech.do.ncf.range"].create(
            {
                "name": "B02 Report Range",
                "document_type_id": cls.doc_b02.id,
                "company_id": cls.company.id,
                "sequence_start": 1,
                "sequence_end": 999,
                "next_sequence": 1,
                "date_from": date.today() - timedelta(days=1),
                "date_to": date.today() + timedelta(days=365),
                "journal_ids": [Command.set(cls.journal_sale.ids)],
            }
        ).action_activate()

    def test_report_607(self):
        partner = self.env["res.partner"].create({"name": "CF Report"})
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(self.tax_18.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "607 Test",
                "report_type": "607",
                "date_from": date.today(),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_generate()
        self.assertGreaterEqual(len(report.line_ids), 1)
        self.assertEqual(report.line_ids[0].ncf, move.justech_do_ncf)
        self.assertEqual(report.state, "done")
        self.assertTrue(report.generated_by_id)
        self.assertTrue(report.generated_at)

    def test_report_608_voided(self):
        partner = self.env["res.partner"].create({"name": "Void Report"})
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 10.0,
                            "tax_ids": [Command.set(self.tax_18.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        move.justech_do_ncf_void_reason = "Report 608 test void"
        move.action_void_ncf()
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "608 Test",
                "report_type": "608",
                "date_from": date.today(),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_generate()
        self.assertEqual(len(report.line_ids), 1)
