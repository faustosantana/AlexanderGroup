from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechMultiCompany(TransactionCase):
    """T-06 — multi-company license isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["justech.license.service"]
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Justech Co B"})

        cls.feature_a = cls.env["justech.feature"].create(
            {
                "code": "multi_co_feature_a",
                "name": "Multi Co Feature A",
                "license_required": True,
            }
        )
        cls.feature_b = cls.env["justech.feature"].create(
            {
                "code": "multi_co_feature_b",
                "name": "Multi Co Feature B",
                "license_required": True,
            }
        )

    def _create_license(self, name, key, feature, company):
        license_rec = self.env["justech.license"].create(
            {
                "name": name,
                "license_key": key,
                "tier": "STD",
                "state": "active",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        self.env["justech.license.feature"].create(
            {"license_id": license_rec.id, "feature_id": feature.id}
        )
        self.env["justech.license.company"].create(
            {"license_id": license_rec.id, "company_id": company.id}
        )
        license_rec.action_activate()
        return license_rec

    def test_company_a_only_sees_own_license(self):
        self._create_license("License A", "JT-STD-MULTIA001", self.feature_a, self.company_a)
        self._create_license("License B", "JT-STD-MULTIB001", self.feature_b, self.company_b)

        self.assertTrue(self.service.is_active("multi_co_feature_a", company=self.company_a))
        self.assertFalse(self.service.is_active("multi_co_feature_a", company=self.company_b))
        self.assertTrue(self.service.is_active("multi_co_feature_b", company=self.company_b))
        self.assertFalse(self.service.is_active("multi_co_feature_b", company=self.company_a))

    def test_orphan_license_not_global(self):
        orphan = self.env["justech.license"].create(
            {
                "name": "Orphan License",
                "license_key": "JT-STD-ORPHAN001",
                "tier": "STD",
                "state": "active",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        self.env["justech.license.feature"].create(
            {"license_id": orphan.id, "feature_id": self.feature_a.id}
        )
        self.assertFalse(self.service.is_active("multi_co_feature_a", company=self.company_a))
        self.assertFalse(self.service.is_active("multi_co_feature_a", company=self.company_b))

    def test_activate_without_companies_raises(self):
        draft = self.env["justech.license"].create(
            {
                "name": "No Company License",
                "license_key": "JT-STD-NOCOMP001",
                "tier": "STD",
                "state": "draft",
            }
        )
        self.env["justech.license.feature"].create(
            {"license_id": draft.id, "feature_id": self.feature_a.id}
        )
        with self.assertRaises(ValidationError):
            draft.action_activate()

    def test_max_companies_blocks_excess(self):
        license_rec = self.env["justech.license"].create(
            {
                "name": "Single Seat License",
                "license_key": "JT-STD-MAXCO001",
                "tier": "STD",
                "state": "draft",
                "max_companies": 1,
            }
        )
        self.env["justech.license.company"].create(
            {"license_id": license_rec.id, "company_id": self.company_a.id}
        )
        with self.assertRaises(ValidationError):
            self.env["justech.license.company"].create(
                {"license_id": license_rec.id, "company_id": self.company_b.id}
            )
