from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.justech_modules.models.justech_license_key_util import (
    hash_license_key,
)
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechHardening(TransactionCase):
    """F31.1.2 — LIFE-01, SEC-01, COMP-02."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["justech.license.service"]
        cls.isolated_co = cls.env["res.company"].create(
            {"name": "Hardening Isolated Co"}
        )
        cls.feature = cls.env["justech.feature"].create(
            {
                "code": "hardening_feature",
                "name": "Hardening Feature",
                "license_required": True,
            }
        )

    def test_expired_license_blocks_is_active(self):
        plain = "JT-STD-HARDEN-EXP001"
        lic = self.env["justech.license"].create(
            {
                "name": "Hardening Expire License",
                "license_key": plain,
                "tier": "STD",
                "state": "draft",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        self.env["justech.license.company"].create(
            {"license_id": lic.id, "company_id": self.isolated_co.id}
        )
        self.env["justech.license.feature"].create(
            {"license_id": lic.id, "feature_id": self.feature.id}
        )
        lic.action_activate()
        self.assertTrue(
            self.service.is_active("hardening_feature", company=self.isolated_co)
        )
        lic.write({"expires_at": date.today() - timedelta(days=1)})
        self.service.clear_license_cache()
        self.assertFalse(
            self.service.is_active("hardening_feature", company=self.isolated_co)
        )

    def test_license_key_stored_as_hash(self):
        plain = "JT-STD-HARDEN-HASH01"
        lic = self.env["justech.license"].create(
            {
                "name": "Hash License",
                "license_key": plain,
                "tier": "STD",
            }
        )
        expected = hash_license_key(self.env, plain)
        self.assertEqual(lic.license_key_hash, expected)
        self.assertNotEqual(lic.license_key_hash, plain)
        self.assertTrue(lic._find_by_license_key(plain))
        self.assertFalse(lic._find_by_license_key("JT-STD-WRONGKEY"))

    def test_max_users_enforced_on_activate(self):
        co = self.env["res.company"].create({"name": "Max Users Hardening Co"})
        group_user = self.env.ref("base.group_user").id
        for idx in range(2):
            self.env["res.users"].create(
                {
                    "name": f"Max Users User {idx}",
                    "login": f"hardening_maxuser_{idx}@test.local",
                    "company_id": co.id,
                    "company_ids": [(6, 0, [co.id])],
                    "group_ids": [(6, 0, [group_user])],
                }
            )
        lic = self.env["justech.license"].create(
            {
                "name": "Max Users License",
                "license_key": "JT-STD-HARDEN-MAX001",
                "tier": "STD",
                "state": "draft",
                "max_users": 1,
            }
        )
        self.env["justech.license.company"].create(
            {"license_id": lic.id, "company_id": co.id}
        )
        self.env["justech.license.feature"].create(
            {
                "license_id": lic.id,
                "feature_id": self.feature.id,
            }
        )
        with self.assertRaises(ValidationError):
            lic.action_activate()

    def test_license_company_duplicate_blocked(self):
        lic = self.env["justech.license"].create(
            {
                "name": "Dup Co License",
                "license_key": "JT-STD-HARDEN-DUP001",
                "tier": "STD",
            }
        )
        self.env["justech.license.company"].create(
            {"license_id": lic.id, "company_id": self.isolated_co.id}
        )
        with self.assertRaises(ValidationError):
            self.env["justech.license.company"].create(
                {"license_id": lic.id, "company_id": self.isolated_co.id}
            )
