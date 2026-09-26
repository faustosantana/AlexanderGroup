from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_alexander_base.models.catalog import (
    operational_companies,
    profile_for_company,
)


@tagged("post_install", "-at_install", "justech_alexander")
class TestMulticompanyTax(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operational = operational_companies(cls.env)
        cls.by_code = {}
        for company in cls.operational:
            profile = profile_for_company(company)
            if profile:
                cls.by_code[profile["code"]] = company
        cls.shared = cls.env["product.template"].search(
            [("active", "=", True), ("company_id", "=", False)], limit=1
        )

    def _assert_shared_product_tax(self, code):
        company = self.by_code.get(code)
        if not company or not self.shared:
            self.skipTest("company %s or shared product missing" % code)
        product = self.shared.with_company(company)
        taxes = product._dx_taxes_for_company(company)
        self.assertTrue(
            taxes,
            "shared product must resolve a sale tax for %s" % company.name,
        )
        self.assertTrue(
            all(tax.company_id == company for tax in taxes),
            "shared product tax must belong to %s" % company.name,
        )
        return taxes

    def test_shared_product_tax_mayuma(self):
        self._assert_shared_product_tax("MAY")

    def test_shared_product_tax_rempart(self):
        self._assert_shared_product_tax("REM")

    def test_shared_product_tax_doralex(self):
        self._assert_shared_product_tax("DOR")

    def test_shared_product_tax_pinaria(self):
        self._assert_shared_product_tax("PIN")

    def test_shared_product_tax_dominion(self):
        self._assert_shared_product_tax("DOM")

    def test_shared_product_tax_blue_elite(self):
        self._assert_shared_product_tax("BLU")

    def test_multicompany_user_tax_access(self):
        if "MAY" not in self.by_code or "REM" not in self.by_code or not self.shared:
            self.skipTest("Mayuma/Rempart or shared product missing")
        mayuma = self.by_code["MAY"]
        rempart = self.by_code["REM"]
        user = self.env["res.users"].search(
            [("share", "=", False), ("company_ids", "in", mayuma.id)], limit=1
        )
        if not user:
            self.skipTest("no internal user with Mayuma")
        raw_ids = self.shared.sudo().taxes_id.ids
        taxes = (
            self.env["account.tax"]
            .with_user(user)
            .with_company(mayuma)
            .with_context(allowed_company_ids=[mayuma.id])
            .browse(raw_ids)
        )
        data = taxes.read(["name", "company_id"])
        self.assertTrue(data)
        self.assertTrue(all(row["company_id"][0] == mayuma.id for row in data))
        self.assertFalse(any(row["company_id"][0] == rempart.id for row in data))

    def test_sales_tax_company_matches_order(self):
        lines = self.env["sale.order.line"].search(
            [("display_type", "=", False), ("tax_ids", "!=", False)], limit=80
        )
        for line in lines:
            company = line.order_id.company_id
            self.assertTrue(
                all(tax.company_id == company for tax in line.tax_ids),
                "sale line %s tax company mismatch" % line.id,
            )

    def test_purchase_tax_company_matches_po(self):
        lines = self.env["purchase.order.line"].search(
            [("display_type", "=", False), ("tax_ids", "!=", False)], limit=80
        )
        for line in lines:
            company = line.order_id.company_id
            self.assertTrue(
                all(tax.company_id == company for tax in line.tax_ids),
                "purchase line %s tax company mismatch" % line.id,
            )

    def test_invoice_tax_company_matches_move(self):
        lines = self.env["account.move.line"].search(
            [
                ("display_type", "=", False),
                ("tax_ids", "!=", False),
                ("move_id.state", "=", "draft"),
            ],
            limit=80,
        )
        for line in lines:
            company = line.move_id.company_id
            self.assertTrue(
                all(tax.company_id == company for tax in line.tax_ids),
                "draft move line %s tax company mismatch" % line.id,
            )
