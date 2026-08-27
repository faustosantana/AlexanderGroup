from datetime import date, timedelta

from odoo.tests import tagged

from odoo.addons.justech_modules.exceptions import JustechLicenseError
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechLicenseService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["justech.license.service"]
        cls.company = cls.env.company
        cls.feature = cls.env["justech.feature"].search(
            [("code", "=", "platform_core")], limit=1
        )
        cls.test_feature = cls.env["justech.feature"].create(
            {
                "code": "test_feature_svc",
                "name": "Test Feature Service",
                "license_required": True,
            }
        )

    def test_platform_core_always_active(self):
        self.assertTrue(self.service.is_active("platform_core"))

    def test_get_feature(self):
        feature = self.service.get_feature("platform_core")
        self.assertTrue(feature)
        self.assertEqual(feature.code, "platform_core")

    def test_require_active_raises(self):
        with self.assertRaises(JustechLicenseError):
            self.service.require_active("test_feature_svc")

    def test_is_active_false_without_license(self):
        self.assertFalse(self.service.is_active("test_feature_svc"))

    def test_validate_license_invalid_key(self):
        result = self.service.validate_license(key="INVALID-KEY")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "invalid_key")

    def test_validate_license_active(self):
        license_rec = self.env["justech.license"].create(
            {
                "name": "DEV Test License",
                "license_key": "JT-STD-TESTKEY001",
                "tier": "STD",
                "state": "active",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        self.env["justech.license.feature"].create(
            {
                "license_id": license_rec.id,
                "feature_id": self.test_feature.id,
            }
        )
        self.env["justech.license.company"].create(
            {
                "license_id": license_rec.id,
                "company_id": self.company.id,
            }
        )
        license_rec.action_activate()

        self.assertTrue(self.service.is_active("test_feature_svc"))
        self.service.require_active("test_feature_svc")

        result = self.service.validate_license(
            key="JT-STD-TESTKEY001",
            feature_code="test_feature_svc",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "ok")

    def test_audit_on_validate(self):
        before = self.env["justech.license.audit"].search_count([])
        self.service.validate_license(key="NOPE")
        after = self.env["justech.license.audit"].search_count([])
        self.assertGreaterEqual(after, before)
