# -*- coding: utf-8 -*-
"""P0.1 — Fuente canónica NCF / dual-write OFF / gate prefijo."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_ncf_sot_p01")
class TestNcfSourceOfTruthP01(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        if cls.company.country_id.code != "DO":
            cls.company.country_id = cls.env.ref("base.do")
        cls.company.justech_do_fiscal_enabled = True
        cls.Config = cls.env["justech.do.fiscal.config.service"]
        cls.FDP = cls.env["justech.do.fiscal.data.provider"]
        cls.Move = cls.env["account.move"]
        if "justech.fiscal.feature.flag" in cls.env:
            flags = cls.env["justech.fiscal.feature.flag"].sudo().search(
                [("code", "=", "ncf_dual_write")]
            )
            # Ensure OFF for tests (bypass readonly via SQL-equivalent write sequence)
            flags.write({"readonly_flag": False})
            flags.write({"enabled": False})

    def test_dual_write_disabled(self):
        self.assertFalse(self.Config.is_dual_write_enabled(self.company))

    def test_sot_issued_vs_received(self):
        sale = self.Move.new({"move_type": "out_invoice", "company_id": self.company.id})
        self.assertEqual(self.Config.get_ncf_source_of_truth(sale), "justech")
        recv = self.Move.new(
            {
                "move_type": "in_invoice",
                "company_id": self.company.id,
                "justech_do_purchase_registration_mode": "received",
            }
        )
        self.assertEqual(self.Config.get_ncf_source_of_truth(recv), "latam")
        issued = self.Move.new(
            {
                "move_type": "in_invoice",
                "company_id": self.company.id,
                "justech_do_purchase_registration_mode": "issued",
            }
        )
        self.assertEqual(self.Config.get_ncf_source_of_truth(issued), "justech")

    def test_latam_mirror_vals_empty_when_dual_write_off(self):
        Sync = self.env["justech.do.ncf.compat.sync.service"]
        move = self.Move.new({"move_type": "out_invoice", "company_id": self.company.id})
        doc = self.env["justech.do.fiscal.document.type"].search(
            [("prefix", "=", "B01")], limit=1
        )
        vals = Sync.latam_mirror_vals(move, "B0100000099", doc)
        self.assertEqual(vals, {})

    def test_prefix_gate_blocks_mismatch(self):
        # Synthetic draft-like recordset using new() + validate method
        LatamType = self.env["l10n_latam.document.type"].search(
            [("doc_code_prefix", "=", "B01")], limit=1
        )
        if not LatamType:
            self.skipTest("No LATAM B01 type")
        move = self.Move.new(
            {
                "move_type": "in_invoice",
                "company_id": self.company.id,
                "justech_do_purchase_registration_mode": "received",
                "l10n_latam_document_type_id": LatamType.id,
                "l10n_latam_document_number": "B0200000099",
            }
        )
        # Bind into a real-like browse by creating in memory check via FDP
        check = self.FDP.check_type_ncf_prefix_consistency(move)
        self.assertFalse(check["ok"])
        with self.assertRaises(UserError):
            # Call gate on empty recordset pattern: use temporary create+rollback
            partner = self.env["res.partner"].create({"name": "P01 Gate Partner"})
            journal = self.env["account.journal"].search(
                [("type", "=", "purchase"), ("company_id", "=", self.company.id)],
                limit=1,
            )
            if not journal:
                self.skipTest("No purchase journal")
            m = self.Move.create(
                {
                    "move_type": "in_invoice",
                    "company_id": self.company.id,
                    "partner_id": partner.id,
                    "journal_id": journal.id,
                    "justech_do_purchase_registration_mode": "received",
                    "l10n_latam_document_type_id": LatamType.id,
                    "l10n_latam_document_number": "B0200000199",
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "line",
                                "quantity": 1,
                                "price_unit": 10,
                            },
                        )
                    ],
                }
            )
            m._justech_validate_type_ncf_prefix_before_post()

    def test_fdp_prefers_justech_ncf(self):
        move = self.Move.new(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "justech_do_ncf": "B0100000555",
                "l10n_latam_document_number": "B0200000666",
            }
        )
        self.assertEqual(self.FDP.get_ncf(move), "B0100000555")
