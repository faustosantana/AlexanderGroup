"""Compras: documentos recibidos (LATAM) vs emitidos (Justech B11/B13/B17)."""
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_purchase_mode")
class TestPurchaseRegistrationMode(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.company.justech_do_fiscal_enabled = True
        cls.product = cls.env["product.product"].create(
            {"name": "Svc Compra", "type": "service", "list_price": 100.0}
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal.write({"justech_do_use_ncf": True})
        cls.doc_b11 = cls.env.ref("justech_l10n_do_base.doc_type_b11")
        cls.doc_b13 = cls.env.ref("justech_l10n_do_base.doc_type_b13")
        cls.doc_b17 = cls.env.ref("justech_l10n_do_base.doc_type_b17")
        cls.doc_b14 = cls.env.ref("justech_l10n_do_base.doc_type_b14")
        cls.Config = cls.env["justech.do.purchase.emission.config"]
        cls.Config.ensure_configs_for_companies(cls.company)
        mgr = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        cls.env.user.write({"group_ids": [(4, mgr.id)]})

    def _line(self):
        return Command.create(
            {
                "name": "Linea",
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
            }
        )

    def _range(self, doc, start=11, end=15):
        today = date.today()
        rng = self.env["justech.do.ncf.range"].create(
            {
                "name": f"Test {doc.prefix}",
                "document_type_id": doc.id,
                "company_id": self.company.id,
                "sequence_start": start,
                "sequence_end": end,
                "next_sequence": start,
                "date_from": today - timedelta(days=1),
                "date_to": today + timedelta(days=365),
                "journal_ids": [Command.set(self.journal.ids)],
            }
        )
        rng.action_activate()
        return rng

    def test_configs_exist_and_b17_without_range_inactive(self):
        for prefix, doc in (
            ("B11", self.doc_b11),
            ("B13", self.doc_b13),
            ("B17", self.doc_b17),
        ):
            cfg = self.Config.get_for(self.company, doc)
            self.assertTrue(cfg, f"Missing config {prefix}")
            self.assertIn(prefix, cfg.name_full)
        cfg17 = self.Config.get_for(self.company, self.doc_b17)
        if not cfg17.range_id:
            self.assertFalse(cfg17.emission_enabled)
            self.assertEqual(cfg17.status, "no_range")

    def test_b14_not_purchase_document(self):
        self.assertFalse(self.doc_b14.is_purchase_ncf())
        self.assertTrue(self.doc_b14.is_sale_ncf())

    def test_received_requires_latam_no_sequence_consume(self):
        if "l10n_latam_document_type_id" not in self.env["account.move"]._fields:
            self.skipTest("LATAM document fields not available")
        LatamModel = "l10n.latam.document.type"
        if LatamModel not in self.env:
            self.skipTest("LATAM document type model not loaded")
        e31 = self.env[LatamModel].search([("doc_code_prefix", "=", "E31")], limit=1)
        if not e31:
            self.skipTest("LATAM E31 not installed")
        vendor = self.env["res.partner"].create({"name": "Prov E31", "supplier_rank": 1})
        b11_next_before = False
        rng = self.env["justech.do.ncf.range"].search(
            [
                ("company_id", "=", self.company.id),
                ("prefix", "=", "B11"),
                ("state", "=", "active"),
            ],
            limit=1,
        )
        if rng:
            b11_next_before = rng.next_sequence
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "journal_id": self.journal.id,
                "invoice_date": date.today(),
                "justech_do_purchase_registration_mode": "received",
                "l10n_latam_document_type_id": e31.id,
                "l10n_latam_document_number": "E310099988877",
                "invoice_line_ids": [self._line()],
            }
        )
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.justech_do_ncf)
        if rng:
            self.assertEqual(rng.next_sequence, b11_next_before)

    def test_b11_issued_consumes_only_on_post(self):
        rng = self._range(self.doc_b11, start=11, end=15)
        self.assertEqual(rng.next_sequence, 11)
        vendor = self.env["res.partner"].create(
            {"name": "Informal", "supplier_rank": 1, "vat": "00112345678"}
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "journal_id": self.journal.id,
                "invoice_date": date.today(),
                "justech_do_purchase_registration_mode": "issued",
                "justech_do_document_type_id": self.doc_b11.id,
                "invoice_line_ids": [self._line()],
            }
        )
        self.assertEqual(rng.next_sequence, 11)
        bill.action_post()
        self.assertTrue(bill.justech_do_ncf.startswith("B11"))
        self.assertEqual(bill.justech_do_ncf, "B1100000011")
        self.assertEqual(rng.next_sequence, 12)

    def test_b17_without_range_blocks_post(self):
        # Ensure no active B17 range for company
        self.env["justech.do.ncf.range"].search(
            [
                ("company_id", "=", self.company.id),
                ("prefix", "=", "B17"),
                ("state", "=", "active"),
            ]
        ).write({"state": "cancelled"})
        vendor = self.env["res.partner"].create({"name": "Foreign", "supplier_rank": 1})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "journal_id": self.journal.id,
                "invoice_date": date.today(),
                "justech_do_purchase_registration_mode": "issued",
                "justech_do_document_type_id": self.doc_b17.id,
                "invoice_line_ids": [self._line()],
            }
        )
        with self.assertRaises(UserError) as err:
            bill.action_post()
        self.assertIn("B17", str(err.exception))
        self.assertIn("rango DGII activo", str(err.exception))
        self.assertFalse(bill.justech_do_ncf)

    def test_display_names_full(self):
        self.assertIn("Proveedor Informal", self.doc_b11.display_name)
        self.assertIn("Gastos Menores", self.doc_b13.display_name)
        self.assertIn("Pagos al Exterior", self.doc_b17.display_name)
        self.assertTrue(self.doc_b11.display_name.startswith("B11"))
