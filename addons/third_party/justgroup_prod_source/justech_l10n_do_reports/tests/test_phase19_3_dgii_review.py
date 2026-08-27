"""Tests Fase 19.3 — bandeja revisión fiscal DGII."""
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPhase193DgiiReview(TransactionCase):
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
        cls.product = cls.env["product.product"].create(
            {
                "name": "P19.3 Review goods",
                "type": "consu",
                "is_storable": True,
                "standard_price": 100.0,
                "supplier_taxes_id": [Command.set(cls.tax_purchase_18.ids)],
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.doc_b11 = cls.env.ref("justech_l10n_do_base.doc_type_b11")
        cls.journal.justech_do_use_ncf = True
        cls.journal.justech_do_default_document_type_id = cls.doc_b11.id
        # Product isolation: Hellenia withholding catalog removed; Justgroup uses justech models
        pass  # sync via justech withholding if available

        cls.fiscal_user = cls.env["res.users"].create(
            {
                "name": "P19.3 Fiscal User",
                "login": f"p193_fiscal_{cls.env.cr.dbname}@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(
                        cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_user").id
                    ),
                    Command.link(cls.env.ref("account.group_account_invoice").id),
                ],
            }
        )
        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "P19.3 Supervisor",
                "login": f"p193_super_{cls.env.cr.dbname}@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(
                        cls.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager").id
                    ),
                    Command.link(cls.env.ref("account.group_account_invoice").id),
                ],
            }
        )

    def _bill(self, partner, ncf):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "invoice_date": date.today(),
                "justech_do_ncf": ncf,
                "justech_do_document_type_id": self.doc_b11.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def test_review_load_and_validate(self):
        partner = self.env["res.partner"].create(
            {"name": "P19.3 Review Vendor", "vat": "131000050", "supplier_rank": 1}
        )
        self._bill(partner, "B1193000001")
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.3 Review 606",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        self.assertTrue(report.line_ids)
        report.action_validate_period()
        self.assertEqual(report.state, "validated")
        self.assertTrue(report.audit_ids)

    def test_exclude_requires_approval_and_blocks_export(self):
        partner = self.env["res.partner"].create(
            {"name": "P19.3 Exclude Vendor", "vat": "131000051", "supplier_rank": 1}
        )
        move = self._bill(partner, "B1193000002")
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.3 Exclude flow",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.with_user(self.fiscal_user).action_load_review_lines()
        report.with_user(self.fiscal_user).action_validate_period()
        line = report.line_ids.filtered(lambda l: l.move_id == move)
        self.assertTrue(line)
        self.env["justech.do.dgii.report.exclude.wizard"].with_user(
            self.fiscal_user
        ).create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "Prueba exclusión 19.3",
            }
        ).action_confirm_exclude()
        self.assertEqual(report.state, "pending_approval")
        self.assertFalse(move.justech_do_include_in_dgii)
        self.assertIn("Prueba exclusión", move.message_ids[0].body)
        with self.assertRaises(AccessError):
            report.with_user(self.fiscal_user).action_generate_dgii_export()

    def test_supervisor_approve_and_generate(self):
        partner = self.env["res.partner"].create(
            {"name": "P19.3 Approve Vendor", "vat": "131000052", "supplier_rank": 1}
        )
        self._bill(partner, "B1193000003")
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.3 Approve flow",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        report.action_validate_period()
        line = report.line_ids.filtered(lambda l: l.fiscal_state == "valid")[:1]
        self.env["justech.do.dgii.report.exclude.wizard"].create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "Exclusión para aprobación",
            }
        ).action_confirm_exclude()
        report.with_user(self.supervisor).action_approve_report()
        self.assertEqual(report.state, "approved")
        report.with_user(self.supervisor).action_generate_dgii_export()
        self.assertEqual(report.state, "generated")
        self.assertTrue(report.export_file_hash)

    def test_reject_restores_inclusion(self):
        partner = self.env["res.partner"].create(
            {"name": "P19.3 Reject Vendor", "vat": "131000053", "supplier_rank": 1}
        )
        move = self._bill(partner, "B1193000004")
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.3 Reject flow",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        line = report.line_ids.filtered(lambda l: l.move_id == move)
        self.env["justech.do.dgii.report.exclude.wizard"].create(
            {
                "report_id": report.id,
                "line_ids": [Command.set(line.ids)],
                "reason": "Exclusión rechazable",
            }
        ).action_confirm_exclude()
        self.env["justech.do.dgii.report.reject.wizard"].with_user(
            self.supervisor
        ).create(
            {"report_id": report.id, "comment": "No procede la exclusión"}
        ).action_confirm_reject()
        self.assertEqual(report.state, "rejected")
        move.invalidate_recordset()
        self.assertTrue(move.justech_do_include_in_dgii)

    def test_exclude_without_reason_fails(self):
        report = self.env["justech.do.fiscal.report"].create(
            {
                "name": "P19.3 No reason",
                "report_type": "606",
                "date_from": date.today().replace(day=1),
                "date_to": date.today(),
                "company_id": self.company.id,
            }
        )
        report.action_load_review_lines()
        line = report.line_ids[:1]
        wizard = self.env["justech.do.dgii.report.exclude.wizard"].create(
            {"report_id": report.id, "line_ids": [Command.set(line.ids)], "reason": "  "}
        )
        with self.assertRaises(UserError):
            wizard.action_confirm_exclude()
