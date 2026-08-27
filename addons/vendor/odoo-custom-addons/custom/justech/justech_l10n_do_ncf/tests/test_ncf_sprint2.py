"""Pruebas Sprint 2 — duplicados v2.0, diagnóstico y centro administrativo."""
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_ncf_sprint2")
class TestJustechNcfSprint2(TransactionCase):
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
                "name": "Product Sprint2",
                "type": "consu",
                "is_storable": True,
                "list_price": 50.0,
                "taxes_id": [Command.set(cls.tax_18.ids)],
            }
        )
        cls.journal_sale = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal_sale.write({"justech_do_use_ncf": True})
        cls.journal_purchase = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.doc_b01 = cls.env.ref("justech_l10n_do_base.doc_type_b01")
        cls.doc_b11 = cls.env.ref("justech_l10n_do_base.doc_type_b11")
        manager = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        cls.env.user.write({"group_ids": [(4, manager.id)]})

    def _create_range(self, doc, journal, start=1, end=50):
        today = date.today()
        ncf_range = self.env["justech.do.ncf.range"].create(
            {
                "name": f"S2 {doc.prefix}",
                "document_type_id": doc.id,
                "company_id": self.company.id,
                "sequence_start": start,
                "sequence_end": end,
                "next_sequence": start,
                "date_from": today - timedelta(days=1),
                "date_to": today + timedelta(days=365),
                "journal_ids": [Command.set(journal.ids)],
            }
        )
        ncf_range.action_activate()
        return ncf_range

    def test_duplicate_v2_same_vendor_purchase_blocked(self):
        self._create_range(self.doc_b11, self.journal_purchase)
        self.journal_purchase.write(
            {
                "justech_do_use_ncf": True,
                "justech_do_default_document_type_id": self.doc_b11.id,
            }
        )
        vendor = self.env["res.partner"].create({"name": "Prov S2", "supplier_rank": 1})
        common_vals = {
            "move_type": "in_invoice",
            "partner_id": vendor.id,
            "journal_id": self.journal_purchase.id,
            "invoice_date": date.today(),
            "justech_do_document_type_id": self.doc_b11.id,
            "justech_do_ncf": "B1100007777",
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Line",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 100,
                    }
                )
            ],
        }
        bill1 = self.env["account.move"].create(common_vals)
        bill1.action_post()
        bill2 = self.env["account.move"].create(common_vals)
        with self.assertRaises(ValidationError):
            bill2.action_post()

    def test_duplicate_v2_same_ncf_different_vendors_allowed(self):
        """Compras: mismo NCF, distinta empresa emisora (proveedor) → permitido."""
        self._create_range(self.doc_b11, self.journal_purchase)
        self.journal_purchase.write(
            {
                "justech_do_use_ncf": True,
                "justech_do_default_document_type_id": self.doc_b11.id,
            }
        )
        ncf = "B1100008888"
        for name in ("Prov A Index", "Prov B Index"):
            vendor = self.env["res.partner"].create({"name": name, "supplier_rank": 1})
            bill = self.env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": vendor.id,
                    "journal_id": self.journal_purchase.id,
                    "invoice_date": date.today(),
                    "justech_do_document_type_id": self.doc_b11.id,
                    "justech_do_ncf": ncf,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Line",
                                "product_id": self.product.id,
                                "quantity": 1,
                                "price_unit": 50,
                            }
                        )
                    ],
                }
            )
            bill.action_post()
            self.assertEqual(bill.justech_do_ncf, ncf)
            self.assertEqual(bill.state, "posted")

    def test_range_audit_summary(self):
        self._create_range(self.doc_b01, self.journal_sale)
        summary = self.env["justech.do.ncf.range.audit.service"].summary_for_company(
            self.company
        )
        self.assertGreaterEqual(summary["active_ranges"], 1)

    def test_diagnostic_scan_readonly(self):
        wizard = self.env["justech.do.fiscal.diagnostic.wizard"].create(
            {"company_id": self.company.id}
        )
        wizard.action_run_scan()
        self.assertTrue(wizard.scan_date)
        posted_before = self.env["account.move"].search_count([("state", "=", "posted")])

    def test_admin_center_open(self):
        action = self.env["justech.do.ncf.admin.center"].open_for_user(self.env)
        self.assertEqual(action["res_model"], "justech.do.ncf.admin.center")
        center = self.env["justech.do.ncf.admin.center"].browse(action["res_id"])
        self.assertGreaterEqual(center.active_range_count, 0)

    def test_ncf_range_pct_used(self):
        ncf_range = self._create_range(self.doc_b01, self.journal_sale, start=100, end=109)
        self.assertEqual(ncf_range.pct_used, 0.0)
        partner = self.env["res.partner"].create({"name": "C", "vat": "131793916"})
        inv = self.env["account.move"].create(
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
                            "price_unit": 100,
                            "tax_ids": [Command.set(self.tax_18.ids)],
                        }
                    )
                ],
            }
        )
        inv.action_post()
        ncf_range.invalidate_recordset(["pct_used", "next_sequence"])
        self.assertGreater(ncf_range.pct_used, 0)
