"""Tests Fase 19 — campos P0 y exportador piloto 606."""
from datetime import date, timedelta

from odoo import Command
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPhase19Dgii606(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.company.justech_do_fiscal_enabled = True
        cls.tax_purchase_18 = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("amount", "=", 18),
                ("type_tax_use", "=", "purchase"),
            ],
            limit=1,
        )
        cls.tax_wh_isr = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("name", "=", "-10% ISR Fee"),
                ("type_tax_use", "=", "purchase"),
            ],
            limit=1,
        )
        cls.product_goods = cls.env["product.product"].create(
            {
                "name": "Bien compra 606",
                "type": "consu",
                "is_storable": True,
                "standard_price": 100.0,
                "supplier_taxes_id": [Command.set(cls.tax_purchase_18.ids)],
            }
        )
        cls.product_service = cls.env["product.product"].create(
            {
                "name": "Servicio compra 606",
                "type": "service",
                "standard_price": 50.0,
                "supplier_taxes_id": [Command.set(cls.tax_purchase_18.ids)],
            }
        )
        cls.journal_purchase = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.doc_b11 = cls.env.ref("justech_l10n_do_base.doc_type_b11")
        cls.journal_purchase.justech_do_use_ncf = True
        cls.journal_purchase.justech_do_default_document_type_id = cls.doc_b11.id
        # Product isolation: Hellenia withholding catalog removed; Justgroup uses justech models
        pass  # sync via justech withholding if available

    def _vendor(self, name, vat):
        return self.env["res.partner"].create(
            {
                "name": name,
                "vat": vat,
                "supplier_rank": 1,
            }
        )

    def _purchase_invoice(self, partner, ncf, lines, move_type="in_invoice", origin_ncf=False):
        vals = {
            "move_type": move_type,
            "partner_id": partner.id,
            "journal_id": self.journal_purchase.id,
            "invoice_date": date.today(),
            "justech_do_ncf": ncf,
            "justech_do_document_type_id": self.doc_b11.id,
            "invoice_line_ids": lines,
        }
        if origin_ncf:
            vals["justech_do_ncf_modified"] = origin_ncf
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move

    def test_partner_id_type_from_vat(self):
        rnc = self._vendor("Formal B11", "131793916")
        self.assertEqual(rnc.justech_do_partner_id_type, "1")
        cedula = self._vendor("Informal B13", "00112345678")
        self.assertEqual(cedula.justech_do_partner_id_type, "2")

    def test_p0_fields_on_move(self):
        partner = self._vendor("Proveedor P0", "131000001")
        move = self._purchase_invoice(
            partner,
            "B1100000001",
            [
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 100.0,
                    }
                )
            ],
        )
        self.assertEqual(move.justech_do_ncf, "B1100000001")
        self.assertEqual(move.justech_do_dgii_line_status, "1")

    def test_validate_606_missing_ncf(self):
        partner = self._vendor("Sin NCF", "131000002")
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_goods.id,
                            "quantity": 1,
                            "price_unit": 10.0,
                        }
                    )
                ],
            }
        )
        move.action_post()
        exporter = self.env["justech.do.dgii.606.exporter"]
        errors = exporter.validate_moves_606(
            self.company, date.today(), date.today()
        )
        self.assertTrue(any("NCF" in err for err in errors))

    def test_export_606_xlsx(self):
        partner = self._vendor("Export 606", "131000003")
        self._purchase_invoice(
            partner,
            "B1100000002",
            [
                Command.create(
                    {
                        "product_id": self.product_service.id,
                        "quantity": 1,
                        "price_unit": 200.0,
                    }
                ),
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 100.0,
                    }
                ),
            ],
        )
        exporter = self.env["justech.do.dgii.606.exporter"]
        content, filename = exporter.export_xlsx(
            self.company, date.today(), date.today()
        )
        self.assertTrue(content)
        self.assertIn("606", filename)
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "606 Test Export",
                "report_type": "606",
                "date_from": date.today(),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_generate()
        report.action_export_dgii_606()
        self.assertTrue(report.export_file)
        self.assertEqual(report.validation_state, "ok")

    def test_withholding_catalog_dgii_code(self):
        catalog = self.env["justech.withholding.catalog"].search(
            [("code", "=", "RET-HON-10"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        self.assertTrue(catalog)
        self.assertEqual(catalog.dgii_withholding_code, "02")

    def test_credit_note_ncf_modified(self):
        partner = self._vendor("NC Proveedor", "131000004")
        origin = self._purchase_invoice(
            partner,
            "B1100000003",
            [
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 50.0,
                    }
                )
            ],
        )
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": date.today(),
                "justech_do_ncf": "B0400000001",
                "justech_do_document_type_id": self.env.ref(
                    "justech_l10n_do_base.doc_type_b04"
                ).id,
                "reversed_entry_id": origin.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_goods.id,
                            "quantity": 1,
                            "price_unit": 50.0,
                        }
                    )
                ],
            }
        )
        refund.action_post()
        self.assertEqual(refund.justech_do_ncf_modified, origin.justech_do_ncf)

    def test_excluded_move_not_exported(self):
        partner = self._vendor("Excluido DGII", "131000010")
        move = self._purchase_invoice(
            partner,
            "B1199000001",
            [
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 75.0,
                    }
                )
            ],
        )
        move.write(
            {
                "justech_do_include_in_dgii": False,
                "justech_do_dgii_exclusion_reason": "Prueba exclusión",
                "justech_do_dgii_fiscal_state": "excluded",
            }
        )
        exporter = self.env["justech.do.dgii.606.exporter"]
        buckets = exporter.classify_moves_606(
            self.company, date.today(), date.today()
        )
        self.assertIn(move, buckets["excluded"])
        self.assertNotIn(move, buckets["valid"])

    def test_validate_period_summary(self):
        partner_ok = self._vendor("Resumen OK", "131000011")
        self._purchase_invoice(
            partner_ok,
            "B1199000002",
            [
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 80.0,
                    }
                )
            ],
        )
        partner_bad = self._vendor("Resumen Bad", "131000012")
        bad = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner_bad.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_goods.id,
                            "quantity": 1,
                            "price_unit": 10.0,
                        }
                    )
                ],
            }
        )
        bad.action_post()
        exporter = self.env["justech.do.dgii.606.exporter"]
        result = exporter.validate_period_606(
            self.company, date.today(), date.today()
        )
        summary = exporter.format_validation_summary(result)
        self.assertIn("Resumen validación 606", summary)
        self.assertGreaterEqual(result["counts"]["valid"], 1)
        self.assertGreaterEqual(result["counts"]["incomplete"], 1)
        self.assertIn(partner_bad.display_name, result["errors_by_partner"])

    def test_export_errors_xlsx(self):
        partner = self._vendor("Errores XLS", "131000013")
        self._purchase_invoice(
            partner,
            "B1199000003",
            [
                Command.create(
                    {
                        "product_id": self.product_goods.id,
                        "quantity": 1,
                        "price_unit": 90.0,
                    }
                )
            ],
        )
        exporter = self.env["justech.do.dgii.606.exporter"]
        content, filename = exporter.export_errors_xlsx(
            self.company, date.today(), date.today()
        )
        self.assertTrue(content)
        self.assertIn("errores", filename)
