from datetime import date, timedelta

from odoo.tests import tagged

from odoo.addons.justech_modules.exceptions import JustechLicenseError
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechAuditLog(TransactionCase):
    """T-07 — audit trail for activation/deactivation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["justech.license.service"]
        cls.company = cls.env.company
        cls.feature = cls.env["justech.feature"].create(
            {
                "code": "audit_feature",
                "name": "Audit Feature",
                "license_required": True,
            }
        )

    def _grant_license(self):
        license_rec = self.env["justech.license"].create(
            {
                "name": "Audit License",
                "license_key": "JT-STD-AUDIT001",
                "tier": "STD",
                "state": "active",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        self.env["justech.license.feature"].create(
            {"license_id": license_rec.id, "feature_id": self.feature.id}
        )
        self.env["justech.license.company"].create(
            {"license_id": license_rec.id, "company_id": self.company.id}
        )
        return license_rec

    def test_activate_writes_audit(self):
        self._grant_license()
        before = self.env["justech.license.audit"].search_count(
            [("action", "=", "activate"), ("feature_id", "=", self.feature.id)]
        )
        self.service.activate_feature("audit_feature")
        after = self.env["justech.license.audit"].search_count(
            [("action", "=", "activate"), ("feature_id", "=", self.feature.id)]
        )
        self.assertEqual(after, before + 1)

    def test_deactivate_writes_audit(self):
        self._grant_license()
        self.service.activate_feature("audit_feature")
        before = self.env["justech.license.audit"].search_count(
            [("action", "=", "deactivate"), ("feature_id", "=", self.feature.id)]
        )
        self.service.deactivate_feature("audit_feature")
        after = self.env["justech.license.audit"].search_count(
            [("action", "=", "deactivate"), ("feature_id", "=", self.feature.id)]
        )
        self.assertEqual(after, before + 1)

    def test_api_version(self):
        self.assertEqual(self.service.get_api_version(), 1)
        self.assertEqual(self.service.API_VERSION, 1)

    def test_deactivate_always_on_raises(self):
        with self.assertRaises(JustechLicenseError):
            self.service.deactivate_feature("platform_core")
