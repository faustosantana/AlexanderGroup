from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.justech_modules.exceptions import JustechLicenseError
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechDependencies(TransactionCase):
    """T-05 — commercial module dependencies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["justech.license.service"]
        cls.company = cls.env.company

        cls.base_module, cls.base_feature = cls.service.register_from_manifest(
            "dep_base_mod",
            {
                "code": "dep_base_mod",
                "feature_code": "dep_base_feature",
                "name": "Dependency Base",
                "license_required": True,
                "always_enabled": False,
                "category": "platform",
            },
        )
        cls.child_module, cls.child_feature = cls.service.register_from_manifest(
            "dep_child_mod",
            {
                "code": "dep_child_mod",
                "feature_code": "dep_child_feature",
                "name": "Dependency Child",
                "license_required": True,
                "always_enabled": False,
                "category": "platform",
            },
        )
        cls.env["justech.module.dependency"].create(
            {
                "module_id": cls.child_module.id,
                "depends_on_module_id": cls.base_module.id,
                "dependency_type": "required",
            }
        )

    def _license_with_features(self, features, companies=None):
        license_rec = self.env["justech.license"].create(
            {
                "name": "Dep Test License",
                "license_key": "JT-STD-DEPCHECK001",
                "tier": "STD",
                "state": "active",
                "expires_at": date.today() + timedelta(days=30),
            }
        )
        for feature in features:
            self.env["justech.license.feature"].create(
                {"license_id": license_rec.id, "feature_id": feature.id}
            )
        for company in companies or [self.company]:
            self.env["justech.license.company"].create(
                {"license_id": license_rec.id, "company_id": company.id}
            )
        return license_rec

    def test_check_dependencies_missing_base(self):
        self._license_with_features([self.child_feature])
        result = self.service.check_dependencies("dep_child_feature")
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"][0]["module_code"], "dep_base_mod")

    def test_activate_feature_blocked_without_dependency(self):
        self._license_with_features([self.child_feature])
        with self.assertRaises(JustechLicenseError):
            self.service.activate_feature("dep_child_feature")

    def test_activate_feature_with_dependency_chain(self):
        license_rec = self._license_with_features(
            [self.base_feature, self.child_feature]
        )
        license_rec.action_activate()
        self.assertTrue(self.service.is_active("dep_base_feature"))
        self.assertTrue(self.service.is_active("dep_child_feature"))
