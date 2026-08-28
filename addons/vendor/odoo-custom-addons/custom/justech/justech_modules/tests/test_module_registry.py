from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechModuleRegistry(TransactionCase):
    def test_platform_module_registered(self):
        module = self.env["justech.module"].search(
            [("code", "=", "justech_modules")], limit=1
        )
        self.assertTrue(module)
        self.assertEqual(module.state, "registered")

    def test_register_from_manifest(self):
        service = self.env["justech.license.service"]
        module, feature = service.register_from_manifest(
            "justech_modules_test",
            {
                "code": "justech_modules_test",
                "feature_code": "test_feature_registry",
                "name": "Test Registry Feature",
                "license_required": True,
                "category": "platform",
            },
        )
        self.assertEqual(module.code, "justech_modules_test")
        self.assertEqual(feature.code, "test_feature_registry")
