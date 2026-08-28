from odoo.tests import tagged

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from odoo.addons.justech_modules.tests.test_admin_access import _provision_test_key


FORBIDDEN_CODES = frozenset(
    {
        "crm",
        "ia",
        "rrhh",
        "activos_fijos",
        "marketplace",
        "manufactura",
        "nomina",
        "ventas",
        "compras",
        "inventario",
        "contabilidad_fiscal_rd",
    }
)


@tagged("post_install", "-at_install", "justech_modules")
class TestClientModuleControl(TransactionCase):
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
        cls.LicenseSvc = cls.env["justech.license.service"]

    def test_only_justech_customizations_visible(self):
        rows = self.LicenseSvc.get_client_module_rows(company=self.env.company)
        self.assertTrue(rows)
        self.assertLessEqual(len(rows), 5)
        main_codes = {r["main_module_code"] for r in rows}
        self.assertFalse(main_codes & FORBIDDEN_CODES)
        self.assertIn("fiscal_rd", main_codes)
        self.assertIn("reportes_documentos_corporativos", main_codes)
        names = " ".join(r["name"] for r in rows).lower()
        for forbidden in ("crm", "marketplace", "manufactura", "nómina", "ventas", "compras"):
            self.assertNotIn(forbidden, names)

    def test_fiscal_rd_grouped_includes(self):
        rows = self.LicenseSvc.get_client_module_rows(company=self.env.company)
        fiscal = next(r for r in rows if r["main_module_code"] == "fiscal_rd")
        includes = fiscal.get("includes") or []
        for label in ("NCF", "B01/B02/B03/B04", "DGII 606", "ITBIS"):
            self.assertIn(label, includes)

    def test_commercial_feature_rows(self):
        rows = self.LicenseSvc.get_commercial_feature_rows(
            "fiscal_rd", company=self.env.company
        )
        self.assertTrue(rows)
        labels = {row["label"] for row in rows}
        self.assertIn("NCF", labels)
        self.assertIn("B01 Crédito Fiscal", labels)

    def test_commercial_feature_toggle_audited(self):
        token = self.env["justech.admin.access.service"].issue_critical_grant(
            self.env["justech.admin.access.service"].CRITICAL_PLATFORM_MUTATION
        )
        svc = self.LicenseSvc.with_context(justech_critical_token=token)
        svc.set_commercial_feature("fiscal_rd", "ncf", self.env.company, False)
        audit = self.env["justech.client.module.audit"].sudo().search(
            [("action", "=", "feature_toggle")], order="id desc", limit=1
        )
        self.assertTrue(audit)
        self.assertEqual(audit.state_before, "ON")
        self.assertEqual(audit.state_after, "OFF")
        self.assertEqual(audit.details.get("feature_key"), "ncf")

    def test_pos_only_when_installed_and_configured(self):
        rows = self.LicenseSvc.get_client_module_rows(company=self.env.company)
        pos_rows = [r for r in rows if r["main_module_code"] == "pos_fiscal_si_instalado"]
        if self.LicenseSvc._odoo_module_installed("hellenia_pos"):
            product = self.LicenseSvc._sudo_internal()["justech.commercial.product"].search(
                [("code", "=", "punto_de_venta")], limit=1
            )
            configured = self.LicenseSvc._product_configured(
                product, self.LicenseSvc._sudo_internal()
            )
            self.assertEqual(bool(pos_rows), configured)
        else:
            self.assertFalse(pos_rows)

    def test_visibility_report(self):
        report = self.LicenseSvc.get_visible_justech_customizations_report()
        self.assertLessEqual(report["visible_count"], 5)
        self.assertTrue(report["visible"])

    def test_unpaid_module_cannot_activate(self):
        with self.assertRaises(Exception) as ctx:
            token = self.env["justech.admin.access.service"].issue_critical_grant(
                self.env["justech.admin.access.service"].CRITICAL_PLATFORM_MUTATION
            )
            self.LicenseSvc.with_context(justech_critical_token=token).execute_client_module_action(
                "activate", "contabilidad_rd", company=self.env.company
            )
        self.assertIn("no está incluido", str(ctx.exception))

    def test_client_user_denied(self):
        client = self.env["res.users"].create(
            {
                "name": "Client",
                "login": "client_module_test2@hellenia.cloud",
                "group_ids": [(6, 0, [])],
            }
        )
        with self.assertRaises(AccessError):
            self.LicenseSvc.with_user(client).get_client_module_rows()
