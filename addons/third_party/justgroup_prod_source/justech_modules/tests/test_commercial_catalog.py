from odoo.tests import tagged

from odoo.tests.common import TransactionCase

from odoo.addons.justech_modules.tests.test_admin_access import _provision_test_key


@tagged("post_install", "-at_install", "justech_modules")
class TestCommercialCatalog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.admin.write(
            {
                "group_ids": [
                    (4, cls.env.ref("justech_modules.group_justech_internal_admin").id)
                ]
            }
        )
        _provision_test_key(cls.env, cls.admin)
        svc = cls.env["justech.admin.access.service"].with_user(cls.admin)
        svc.open_session("TEST-KEY-12345678", scope=svc.SCOPE_ADMIN)
        cls.env = cls.env(user=cls.admin)

    def test_commercial_catalog_has_products(self):
        catalog = self.env["justech.license.service"].get_commercial_catalog()
        self.assertTrue(catalog)
        codes = {row["product_code"] for row in catalog}
        self.assertIn("contabilidad_rd", codes)
        self.assertIn("punto_de_venta", codes)

    def test_no_technical_names_in_commercial_catalog(self):
        catalog = self.env["justech.license.service"].get_commercial_catalog()
        for row in catalog:
            self.assertNotIn("justech_modules", row["name"].lower())
            self.assertNotIn("hellenia_account", row["name"])
            for feat in row["features"]:
                self.assertTrue(feat["commercial_name"])
                self.assertNotEqual(feat["commercial_name"], feat["feature_code"])

    def test_commercial_name_resolver(self):
        svc = self.env["justech.license.service"]
        name = svc.commercial_name_for_feature("l10n_do_ncf")
        self.assertEqual(name, "NCF")
