from odoo.tests import tagged

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


def _provision_test_key(env, user, plain_key="TEST-KEY-12345678", access_level="manager"):
    access = env["justech.admin.access"].sudo().ensure_access_shell(
        user, company=env.company, access_level=access_level
    )
    access.set_key_hash(plain_key)
    return access, plain_key


@tagged("post_install", "-at_install", "justech_modules")
class TestAdminAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Access = cls.env["justech.admin.access"].sudo()
        cls.AccessSvc = cls.env["justech.admin.access.service"]
        cls.LicenseSvc = cls.env["justech.license.service"]
        cls.internal_group = cls.env.ref("justech_modules.group_justech_internal_admin")
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Justech Internal Tester",
                "login": "justech_internal_test@justech.do",
                "group_ids": [(6, 0, [cls.internal_group.id])],
            }
        )
        cls.access, cls.plain_key = _provision_test_key(
            cls.env, cls.internal_user, access_level="manager"
        )

    def _as_internal(self):
        return self.AccessSvc.with_user(self.internal_user)

    def _open_platform_session(self):
        svc = self._as_internal()
        svc.open_session(self.plain_key, scope=svc.SCOPE_PLATFORM)

    def test_admin_key_hash_not_plaintext(self):
        self.assertNotEqual(self.access.key_hash, self.plain_key)
        self.assertTrue(self.access.key_fingerprint.startswith("JA-"))

    def test_no_key_blocks_access(self):
        user = self.env["res.users"].create(
            {
                "name": "No Key User",
                "login": "no_key_test@justech.do",
                "group_ids": [(6, 0, [self.internal_group.id])],
            }
        )
        self.Access.ensure_access_shell(user, company=self.env.company)
        svc = self.AccessSvc.with_user(user)
        with self.assertRaises(UserError) as ctx:
            svc.open_session("ANY-KEY-12345678", scope=svc.SCOPE_PLATFORM)
        self.assertIn("Debe crear una Clave Administrativa Justech", str(ctx.exception))

    def test_invalid_key_rejected(self):
        svc = self._as_internal()
        with self.assertRaises(UserError):
            svc.open_session("WRONG-KEY-99999999", scope=svc.SCOPE_PLATFORM)

    def test_verify_key_increments_failures(self):
        failed_before = self.access.failed_attempts
        ok, reason = self.access.verify_key("WRONG-KEY-99999999")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid")
        self.assertEqual(self.access.failed_attempts, failed_before + 1)

    def test_valid_key_opens_session(self):
        svc = self._as_internal()
        svc.open_session(self.plain_key, scope=svc.SCOPE_PLATFORM)
        self.assertTrue(svc.is_session_valid(scope=svc.SCOPE_PLATFORM))

    def test_revalidate_key_deactivates_prior_session(self):
        """Regression BUGFIX-ADMINKEY-1: second Validar must not require session write ACL."""
        svc = self._as_internal()
        svc.open_session(self.plain_key, scope=svc.SCOPE_ADMIN)
        svc.open_session(self.plain_key, scope=svc.SCOPE_ADMIN)
        self.assertTrue(svc.is_session_valid(scope=svc.SCOPE_ADMIN))

    def test_license_manager_can_open_admin_session(self):
        mgr_group = self.env.ref("justech_modules.group_justech_license_manager")
        mgr_user = self.env["res.users"].create(
            {
                "name": "License Manager Tester",
                "login": "license_mgr_adminkey_test@justech.do",
                "group_ids": [(6, 0, [mgr_group.id])],
            }
        )
        _provision_test_key(self.env, mgr_user)
        svc = self.AccessSvc.with_user(mgr_user)
        svc.open_session("TEST-KEY-12345678", scope=svc.SCOPE_ADMIN)
        self.assertTrue(svc.is_session_valid(scope=svc.SCOPE_ADMIN))

    def test_catalog_requires_session(self):
        with self.assertRaises(AccessError):
            self.LicenseSvc.with_user(self.internal_user).get_activation_catalog()

    def test_catalog_with_session(self):
        self._open_platform_session()
        catalog = self.LicenseSvc.with_user(self.internal_user).get_activation_catalog()
        self.assertTrue(any(row["module_code"] == "justech_modules" for row in catalog))

    def test_critical_action_prompts_step_up(self):
        self._open_platform_session()
        wizard = (
            self.env["justech.module.activation.wizard"]
            .with_user(self.internal_user)
            .create({"company_id": self.env.company.id})
        )
        result = wizard.action_activate_selected()
        self.assertEqual(result.get("res_model"), "justech.admin.stepup.wizard")

    def test_wizard_client_denied(self):
        client = self.env["res.users"].create(
            {
                "name": "Client User",
                "login": "client_test@hellenia.cloud",
                "group_ids": [(6, 0, [])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["justech.module.activation.wizard"].with_user(client).create({})

    def test_wizard_loads_with_session_no_internal_m2o(self):
        self._open_platform_session()
        wizard = (
            self.env["justech.module.activation.wizard"]
            .with_user(self.internal_user)
            .create({"company_id": self.env.company.id})
        )
        self.assertTrue(wizard.line_ids)
        line_fields = self.env["justech.module.activation.wizard.line"]._fields
        self.assertNotIn("feature_id", line_fields)
        self.assertNotIn("module_id", line_fields)
        self.assertIn("feature_code", line_fields)

    def test_security_revoke_clears_keys_and_sessions(self):
        self._open_platform_session()
        self.Access.security_revoke_all_keys_and_sessions()
        self.access.invalidate_recordset()
        self.assertFalse(self.access.has_key)
        svc = self._as_internal()
        self.assertFalse(svc.is_session_valid(scope=svc.SCOPE_PLATFORM))
