"""Pruebas Sprint 2 parte 2 — flujos NC/ND/compras, reglas Adel, multiempresa."""
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_ncf_sprint2b")
class TestJustechNcfSprint2Part2(TransactionCase):
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
        cls.tax_0 = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("amount", "=", 0),
                ("type_tax_use", "=", "sale"),
            ],
            limit=1,
        )
        if not cls.tax_0:
            cls.tax_0 = cls.env["account.tax"].create(
                {
                    "name": "ITBIS 0% Test",
                    "amount": 0,
                    "type_tax_use": "sale",
                    "company_id": cls.company.id,
                }
            )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product S2B",
                "type": "consu",
                "is_storable": True,
                "list_price": 100.0,
                "taxes_id": [Command.set(cls.tax_18.ids)],
            }
        )
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Service Export",
                "type": "service",
                "list_price": 500.0,
                "taxes_id": [Command.set(cls.tax_0.ids)],
            }
        )
        cls.journal_sale = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal_sale.write({"justech_do_use_ncf": True})
        cls.journal_purchase = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.doc_b02 = cls.env.ref("justech_l10n_do_base.doc_type_b02")
        cls.doc_b03 = cls.env.ref("justech_l10n_do_base.doc_type_b03")
        cls.doc_b04 = cls.env.ref("justech_l10n_do_base.doc_type_b04")
        cls.doc_b11 = cls.env.ref("justech_l10n_do_base.doc_type_b11")
        cls.doc_b14 = cls.env.ref("justech_l10n_do_base.doc_type_b14")
        cls.doc_b16 = cls.env.ref("justech_l10n_do_base.doc_type_b16")
        manager = cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager")
        cls.env.user.write({"group_ids": [(4, manager.id)]})

    def _range(self, doc, journal=None, **kw):
        journal = journal or self.journal_sale
        today = date.today()
        r = self.env["justech.do.ncf.range"].create(
            {
                "name": f"S2B {doc.prefix}",
                "document_type_id": doc.id,
                "company_id": self.company.id,
                "sequence_start": kw.get("start", 1),
                "sequence_end": kw.get("end", 100),
                "next_sequence": kw.get("start", 1),
                "date_from": today - timedelta(days=1),
                "date_to": today + timedelta(days=365),
                "journal_ids": [Command.set(journal.ids)],
            }
        )
        r.action_activate()
        return r

    def _sale_inv(self, partner, doc=None, price=100.0, product=None, taxes=None):
        product = product or self.product
        taxes = taxes if taxes is not None else self.tax_18
        vals = {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal_sale.id,
            "invoice_date": date.today(),
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "price_unit": price,
                        "tax_ids": [Command.set(taxes.ids)],
                    }
                )
            ],
        }
        if doc:
            vals["justech_do_document_type_id"] = doc.id
        return self.env["account.move"].create(vals)

    def test_debit_note_b03(self):
        self._range(self.doc_b02)
        self._range(self.doc_b03)
        partner = self.env["res.partner"].create({"name": "ND Client"})
        inv = self._sale_inv(partner, self.doc_b02)
        inv.action_post()
        debit = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "debit_origin_id": inv.id,
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
        debit.action_post()
        self.assertTrue(debit.justech_do_ncf.startswith("B03"))

    def test_purchase_refund_in_refund_origin_ncf(self):
        self._range(self.doc_b11, journal=self.journal_purchase)
        self.journal_purchase.write(
            {
                "justech_do_use_ncf": True,
                "justech_do_default_document_type_id": self.doc_b11.id,
            }
        )
        vendor = self.env["res.partner"].create({"name": "Prov Refund", "supplier_rank": 1})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Purchase line",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 200.0,
                        }
                    )
                ],
            }
        )
        bill.action_post()
        self.assertTrue(bill.justech_do_ncf.startswith("B11"))
        refund = bill._reverse_moves(
            default_values_list=[{"move_type": "in_refund", "invoice_date": date.today()}]
        )
        refund.action_post()
        self.assertEqual(refund.justech_do_origin_ncf, bill.justech_do_ncf)
        self.assertEqual(refund.justech_do_ncf_modified, bill.justech_do_ncf)

    def test_b14_blocks_itbis(self):
        self._range(self.doc_b14)
        partner = self.env["res.partner"].create({"name": "Reg Esp", "vat": "131793916"})
        inv = self._sale_inv(partner, self.doc_b14)
        with self.assertRaises(UserError):
            inv.action_post()

    def test_b14_allows_zero_tax(self):
        self._range(self.doc_b14)
        partner = self.env["res.partner"].create({"name": "Reg Esp", "vat": "131793916"})
        inv = self._sale_inv(partner, self.doc_b14, taxes=self.tax_0)
        inv.action_post()
        self.assertTrue(inv.justech_do_ncf.startswith("B14"))

    def test_high_amount_b02_requires_rnc(self):
        self._range(self.doc_b02)
        partner = self.env["res.partner"].create({"name": "Consumidor Alto"})
        inv = self._sale_inv(partner, self.doc_b02, price=250_000.0)
        with self.assertRaises(UserError):
            inv.action_post()

    def test_export_b16_foreign_partner(self):
        self._range(self.doc_b16)
        country_us = self.env.ref("base.us")
        partner = self.env["res.partner"].create(
            {"name": "Export USA", "country_id": country_us.id, "vat": "131793916"}
        )
        inv = self._sale_inv(partner, self.doc_b16, product=self.service_product, taxes=self.tax_0)
        inv.action_post()
        self.assertTrue(inv.justech_do_ncf.startswith("B16"))

    def test_export_b16_blocks_domestic_partner(self):
        self._range(self.doc_b16)
        partner = self.env["res.partner"].create({"name": "Local", "vat": "131793916"})
        inv = self._sale_inv(partner, self.doc_b16, product=self.service_product, taxes=self.tax_0)
        with self.assertRaises(UserError):
            inv.action_post()

    def test_multi_company_four_isolated_ranges(self):
        companies = [self.company]
        for i in range(3):
            companies.append(
                self.env["res.company"].create(
                    {
                        "name": f"Justech Lab Co {i + 2}",
                        "country_id": self.env.ref("base.do").id,
                        "justech_do_fiscal_enabled": True,
                    }
                )
            )
        self.assertEqual(len(companies), 4)
        Range = self.env["justech.do.ncf.range"]
        for idx, co in enumerate(companies):
            journal = self.env["account.journal"].with_company(co).search(
                [("type", "=", "sale"), ("company_id", "=", co.id)], limit=1
            )
            if not journal:
                journal = self.env["account.journal"].with_company(co).create(
                    {
                        "name": f"Ventas Lab {idx}",
                        "code": f"Z{idx}L",
                        "type": "sale",
                        "company_id": co.id,
                    }
                )
            journal.write({"justech_do_use_ncf": True})
            tax = self.env["account.tax"].with_company(co).search(
                [
                    ("company_id", "=", co.id),
                    ("amount", "=", 18),
                    ("type_tax_use", "=", "sale"),
                ],
                limit=1,
            )
            today = date.today()
            ncf_range = Range.with_company(co).create(
                {
                    "name": f"Co{idx} B02",
                    "document_type_id": self.doc_b02.id,
                    "company_id": co.id,
                    "sequence_start": 2000 + idx * 100,
                    "sequence_end": 2000 + idx * 100 + 10,
                    "next_sequence": 2000 + idx * 100,
                    "date_from": today - timedelta(days=1),
                    "date_to": today + timedelta(days=365),
                    "journal_ids": [Command.set(journal.ids)],
                }
            )
            ncf_range.action_activate()
            self.assertEqual(ncf_range.company_id, co)
            income = self.env["account.account"].with_company(co).search(
                [("company_ids", "in", co.id), ("account_type", "=", "income")],
                limit=1,
            )
            if not income:
                continue
            partner = self.env["res.partner"].create({"name": f"CF Co{idx}"})
            inv = self.env["account.move"].with_company(co).create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "journal_id": journal.id,
                    "invoice_date": date.today(),
                    "justech_do_document_type_id": self.doc_b02.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Línea multiempresa",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "account_id": income.id,
                                "tax_ids": [Command.set(tax.ids)] if tax else [],
                            }
                        )
                    ],
                }
            )
            inv.action_post()
            self.assertEqual(inv.company_id, co)
            self.assertTrue(inv.justech_do_ncf.startswith("B02"))
            found = Range.with_company(co).search(
                [("company_id", "=", co.id), ("state", "=", "active")]
            )
            self.assertTrue(found)
            self.assertTrue(all(r.company_id == co for r in found))
        posted = self.env["account.move"].search_count(
            [
                ("company_id", "in", [c.id for c in companies]),
                ("justech_do_ncf", "!=", False),
                ("state", "=", "posted"),
            ]
        )
        self.assertGreaterEqual(posted, 1)
        for co in companies:
            self.assertGreaterEqual(
                Range.search_count([("company_id", "=", co.id), ("state", "=", "active")]),
                1,
            )
