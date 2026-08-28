from odoo.tests import tagged

from odoo.tests.common import TransactionCase

from odoo.addons.justech_modules.tests.test_admin_access import _provision_test_key


@tagged("post_install", "-at_install", "justech_modules")
class TestActivationWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Access = cls.env["justech.admin.access"].sudo()
        cls.admin = cls.env.ref("base.user_admin")
        cls.admin.write(
            {
                "group_ids": [
                    (4, cls.env.ref("justech_modules.group_justech_internal_admin").id)
                ]
            }
        )
        cls._access, cls._key = _provision_test_key(cls.env, cls.admin)
        svc = cls.env["justech.admin.access.service"].with_user(cls.admin)
        svc.open_session(cls._key, scope=svc.SCOPE_PLATFORM)

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def test_get_activation_catalog_includes_platform(self):
        service = self.env["justech.license.service"]
        catalog = service.get_activation_catalog(company=self.env.company)
        codes = {row["module_code"] for row in catalog}
        self.assertIn("justech_modules", codes)

    def test_wizard_loads_lines(self):
        wizard = self.env["justech.module.activation.wizard"].create(
            {"company_id": self.env.company.id}
        )
        self.assertTrue(wizard.line_ids)
        module_lines = wizard.line_ids.filtered(lambda l: l.line_type == "module")
        self.assertTrue(module_lines)

    def test_register_v2_always_enabled(self):
        service = self.env["justech.license.service"]
        module, features = service.register_from_manifest(
            "justech_modules_test",
            {
                "module_code": "test_v2_module",
                "module_name": "Test V2",
                "category": "platform",
                "always_enabled": True,
                "features": [
                    {"code": "test_v2_feature", "name": "Test V2 Feature"},
                ],
                "dependencies": [],
            },
        )
        self.assertEqual(module.code, "test_v2_module")
        self.assertEqual(len(features), 1)
        feature = features[0]
        self.assertFalse(feature.license_required)
        self.assertTrue(feature.default_active)
        self.assertTrue(
            service.is_active("test_v2_feature", company=self.env.company)
        )
