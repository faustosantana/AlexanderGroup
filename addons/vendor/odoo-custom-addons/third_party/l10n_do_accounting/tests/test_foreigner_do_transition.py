# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_do_accounting")
class TestForeignerDoTransition(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.do = cls.env.ref("base.do")
        cls.ar = cls.env.ref("base.ar")
        cls.Partner = cls.env["res.partner"]

    def test_foreigner_partner_can_transition_to_dominican(self):
        partner = self.Partner.create(
            {
                "name": "UAT ALARMAS FOREIGNER FIX",
                "is_company": True,
                "country_id": self.ar.id,
                "vat": "101503114",
            }
        )
        self.assertEqual(partner.l10n_do_dgii_tax_payer_type, "foreigner")

        partner.write({"country_id": self.do.id})

        self.assertEqual(partner.country_id, self.do)
        self.assertNotEqual(partner.l10n_do_dgii_tax_payer_type, "foreigner")
        # Canonical soft classify for 9-digit RNC starting with 1
        self.assertEqual(partner.l10n_do_dgii_tax_payer_type, "taxpayer")

        if "justech_do_is_dominican" in partner._fields:
            self.assertTrue(partner.justech_do_is_dominican)
        if "justech_do_show_rnc_validation" in partner._fields:
            self.assertTrue(partner.justech_do_show_rnc_validation)

    def test_real_foreigner_remains_valid(self):
        partner = self.Partner.create(
            {
                "name": "UAT REAL FOREIGNER AR",
                "is_company": True,
                "country_id": self.ar.id,
                "vat": "30712345678",
            }
        )
        self.assertEqual(partner.l10n_do_dgii_tax_payer_type, "foreigner")
        partner.write({"name": "UAT REAL FOREIGNER AR UPDATED"})
        self.assertEqual(partner.l10n_do_dgii_tax_payer_type, "foreigner")

    def test_invalid_do_foreigner_final_state_blocked(self):
        partner = self.Partner.create(
            {
                "name": "UAT DO TAXPAYER",
                "is_company": True,
                "country_id": self.do.id,
                "vat": "101010101",
            }
        )
        self.assertNotEqual(partner.l10n_do_dgii_tax_payer_type, "foreigner")
        with self.assertRaises(UserError):
            partner.write({"l10n_do_dgii_tax_payer_type": "foreigner"})
