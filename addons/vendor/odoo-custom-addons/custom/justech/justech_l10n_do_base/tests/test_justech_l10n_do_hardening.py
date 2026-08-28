from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechL10nDoBaseHardening(TransactionCase):
    def test_fiscal_document_type_record_rule(self):
        rules = self.env["ir.rule"].search(
            [("model_id.model", "=", "justech.do.fiscal.document.type")]
        )
        self.assertTrue(
            rules.filtered(lambda r: "company_ids" in (r.domain_force or ""))
        )

    def test_fiscal_document_types_are_shared_catalog(self):
        types = self.env["justech.do.fiscal.document.type"].search([])
        self.assertTrue(types)
        self.assertFalse(types.filtered("company_id"))

    def test_shared_catalog_readable_with_single_company_context(self):
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) < 2:
            self.skipTest("Need at least two companies")
        Doc = self.env["justech.do.fiscal.document.type"]
        b14 = Doc.get_by_prefix("B14")
        self.assertTrue(b14)
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Omni Operative Catalog Test",
                    "login": "omni_catalog_test_user@example.com",
                    "company_id": companies[1].id,
                    "company_ids": [(6, 0, [companies[1].id])],
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("account.group_account_invoice").id,
                                self.env.ref("sales_team.group_sale_salesman").id,
                            ],
                        )
                    ],
                }
            )
        )
        env_user = Doc.with_user(user).with_company(companies[1])
        try:
            env_user.browse(b14.ids).check_access("read")
            read_ok = bool(env_user.browse(b14.ids).read(["prefix", "name"]))
        except AccessError:
            read_ok = False
        self.assertTrue(read_ok)
