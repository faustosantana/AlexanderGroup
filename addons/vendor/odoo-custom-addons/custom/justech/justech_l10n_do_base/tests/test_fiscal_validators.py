"""Pruebas Odoo de validadores fiscales (post_install)."""
from odoo.tests import tagged

from odoo.addons.justech_l10n_do_base.validators import fiscal_context, ncf_format, rnc_format
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_fiscal_validators")
class TestFiscalValidators(TransactionCase):
    def test_rnc_service_delegation(self):
        svc = self.env["justech.do.fiscal.validator.service"]
        self.assertTrue(svc.is_valid_rnc_format("131-793-916"))
        self.assertEqual(svc.normalize_vat("131-793-916"), "131793916")

    def test_ncf_service_delegation(self):
        svc = self.env["justech.do.fiscal.validator.service"]
        ncf = svc.validate_ncf_format("B0100000099")
        self.assertEqual(ncf, "B0100000099")
        prefix, seq = svc.parse_ncf(ncf)
        self.assertEqual(prefix, "B01")
        self.assertEqual(seq, 99)

    def test_fiscal_config_service(self):
        company = self.env.company
        if company.country_id.code != "DO":
            company.country_id = self.env.ref("base.do")
        company.justech_do_fiscal_enabled = True
        svc = self.env["justech.do.fiscal.config.service"]
        self.assertTrue(svc.is_fiscal_enabled(company))

    def test_pure_validators_match_service(self):
        svc = self.env["justech.do.fiscal.validator.service"]
        ncf = "B0200000123"
        self.assertEqual(svc.parse_ncf(ncf), ncf_format.parse_ncf(ncf))
        key = svc.fiscal_duplicate_key_v2(
            self.env.company,
            self.env["account.move"].new({"move_type": "out_invoice", "partner_id": False}),
            ncf,
        )
        expected = fiscal_context.fiscal_duplicate_key_v2(
            company_id=self.env.company.id,
            move_type="out_invoice",
            ncf=ncf,
            company_vat=self.env.company.vat or "",
            partner_vat="",
        )
        self.assertEqual(key, expected)
