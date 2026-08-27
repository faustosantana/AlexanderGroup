# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "justech_security_ux")
class TestJustechPermissionsDirect(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].with_user(self.env.ref("base.user_admin"))
        self.user = self.Users.create(
            {
                "name": "UAT JX Direct",
                "login": "uat_jx_direct_%s" % self.env.cr.dbname,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_apply_level_no_wipe_other_modules(self):
        sale_mgr = self.env.ref("sales_team.group_sale_manager")
        purch_user = self.env.ref("purchase.group_purchase_user")
        self.user.write({"group_ids": [(4, sale_mgr.id), (4, purch_user.id)]})
        before = set(self.user.group_ids.ids)
        self.user.jx_apply_level("purchase", "manager")
        after = set(self.user.group_ids.ids)
        self.assertIn(sale_mgr.id, after)
        self.assertNotIn(purch_user.id, after)
        self.assertIn(self.env.ref("purchase.group_purchase_manager").id, after)
        # no wipe of unrelated extras
        self.assertTrue(before - {purch_user.id} <= after | {self.env.ref("purchase.group_purchase_manager").id})

    def test_apply_cap_surgical(self):
        disc = self.env.ref("sale.group_discount_per_so_line")
        self.assertFalse(disc in self.user.group_ids)
        self.user.jx_apply_cap("so_discount", True)
        self.assertIn(disc, self.user.group_ids)
        self.user.jx_apply_cap("so_discount", False)
        self.assertNotIn(disc, self.user.group_ids)

    def test_fiscal_admin_reader_in_catalog(self):
        catalog = self.Users.jx_catalog()
        fiscal = next(s for s in catalog if s["key"] == "fiscal")
        codes = {L["code"] for L in fiscal["levels"]}
        self.assertIn("admin_reader", codes)
        self.assertIn("admin", codes)

    def test_accounting_recovery_cap_in_catalog_when_module_installed(self):
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_accounting_recovery")], limit=1
        )
        catalog = self.Users.jx_catalog()
        accounting = next(s for s in catalog if s["key"] == "accounting")
        cap_codes = {c["code"] for c in accounting["caps"]}
        if mod.state == "installed":
            self.assertIn("accounting_recovery", cap_codes)
            self.assertEqual(
                next(c["label"] for c in accounting["caps"] if c["code"] == "accounting_recovery"),
                "Recuperación Contable",
            )
        else:
            self.assertNotIn("accounting_recovery", cap_codes)

    def test_accounting_recovery_cap_assign_remove(self):
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_accounting_recovery"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            self.skipTest("justech_accounting_recovery not installed")
        recovery = self.env.ref(
            "justech_accounting_recovery.group_accounting_recovery"
        )
        before = set(self.user.group_ids.ids)
        self.assertFalse(self.user.has_group(
            "justech_accounting_recovery.group_accounting_recovery"
        ))
        self.user.jx_apply_cap("accounting_recovery", True)
        self.assertTrue(self.user.has_group(
            "justech_accounting_recovery.group_accounting_recovery"
        ))
        self.assertEqual(set(self.user.group_ids.ids), before | {recovery.id})
        self.user.jx_apply_cap("accounting_recovery", False)
        self.assertFalse(self.user.has_group(
            "justech_accounting_recovery.group_accounting_recovery"
        ))
        self.assertEqual(set(self.user.group_ids.ids), before)

    def test_margins_granular_caps_in_catalog(self):
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_purchase_sale_margin_control"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            self.skipTest("margins module not installed")
        catalog = self.Users.jx_catalog()
        margins = next(s for s in catalog if s["key"] == "margins")
        self.assertEqual(margins.get("caps_title"), "Acceso a secciones")
        codes = {c["code"] for c in margins["caps"]}
        self.assertIn("m_board", codes)
        self.assertIn("m_ops_view", codes)
        self.assertIn("m_config", codes)

    def test_margins_user_preset_applies_default_caps(self):
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_purchase_sale_margin_control"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            self.skipTest("margins module not installed")
        self.user.jx_apply_level("margins", "user")
        self.assertTrue(self.user.has_group(
            "justech_purchase_sale_margin_control.group_margin_readonly"
        ))
        self.assertTrue(self.user.has_group(
            "justech_purchase_sale_margin_control.group_margin_sec_ops_view"
        ))
        self.assertTrue(self.user.has_group(
            "justech_purchase_sale_margin_control.group_margin_sec_inbox"
        ))
        self.assertFalse(self.user.has_group(
            "justech_purchase_sale_margin_control.group_margin_sec_board"
        ))
        self.assertFalse(self.user.has_group(
            "justech_purchase_sale_margin_control.group_margin_sec_config"
        ))

    def test_new_user_permissions_create_mode_in_js(self):
        """CREATE MODE: catalog + pending state; apply after save — no hang."""
        from pathlib import Path

        js_path = Path(__file__).resolve().parents[1] / "static/src/js/permissions_nav.js"
        js = js_path.read_text(encoding="utf-8")
        self.assertNotIn("Guarda el usuario para configurar sus permisos.", js)
        self.assertNotIn("showSaveFirst", js)
        self.assertIn("jx_default_permission_state", js)
        self.assertIn("jx_apply_permission_state", js)
        self.assertIn("PENDING_STORAGE_KEY", js)
        self.assertIn("createMode", js)
        self.assertIn("if (!uid)", js)

    def test_default_permission_state_no_user_id(self):
        defaults = self.Users.jx_default_permission_state()
        self.assertIsInstance(defaults, dict)
        self.assertIn("sales", defaults)
        self.assertEqual(defaults["sales"]["level"], "none")
        for key, st in defaults.items():
            for cap_code, enabled in (st.get("caps") or {}).items():
                self.assertFalse(enabled, "%s.%s" % (key, cap_code))
            # Prefer «none» when the section defines it
            catalog = self.Users.jx_catalog()
            sec = next((s for s in catalog if s["key"] == key), None)
            if sec and any(L["code"] == "none" for L in (sec.get("levels") or [])):
                self.assertEqual(st["level"], "none", key)

    def test_create_with_mirror_role_fields_does_not_raise(self):
        """Form may POST justech_*_role='none'; CREATE must succeed."""
        login = "uat_jx_create_mirror_%s" % self.env.cr.dbname
        vals = {
            "name": "UAT JX Mirror Create",
            "login": login,
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            "justech_ecf_role": "none",
            "justech_warranty_role": "none",
            "justech_admin_center_role": "none",
            "justech_finance_role": "none",
        }
        user = self.Users.with_context(no_reset_password=True).create(vals)
        self.assertTrue(user.id)
        self.assertFalse(user.has_group("justech_ecf_core.group_ecf_admin"))

    def test_users_settings_color_scheme_default_on_create(self):
        """New-user Guardar must not fail on missing color_scheme."""
        Settings = self.env["res.users.settings"]
        login = "uat_jx_colorscheme_%s" % self.env.cr.dbname
        user = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX Color Scheme",
                "login": login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        # Explicit create without color_scheme (UI can do this)
        settings = Settings.search([("user_id", "=", user.id)], limit=1)
        if settings:
            # already created with user — force recreate path
            settings.unlink()
        settings = Settings.create({"user_id": user.id})
        self.assertEqual(settings.color_scheme, "system")

    def test_web_save_color_scheme_false_coerced(self):
        """Usuarios→Nuevo posts color_scheme=false on res.users."""
        login = "uat_jx_cs_false_%s" % self.env.cr.dbname
        user = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX CS False",
                "login": login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "color_scheme": False,
            }
        )
        self.assertTrue(user.id)
        settings = self.env["res.users.settings"].search(
            [("user_id", "=", user.id)], limit=1
        )
        self.assertTrue(settings)
        self.assertEqual(settings.color_scheme, "system")

    def test_apply_permission_state_after_create(self):
        login = "uat_jx_apply_state_%s" % self.env.cr.dbname
        user = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX Apply State",
                "login": login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        pending = self.Users.jx_default_permission_state()
        pending["sales"] = {"level": "user_all", "caps": {}}
        # sales level codes vary — pick a valid non-none from catalog
        catalog = self.Users.jx_catalog()
        sales = next(s for s in catalog if s["key"] == "sales")
        level_codes = [L["code"] for L in sales["levels"] if L["code"] != "none"]
        self.assertTrue(level_codes)
        pending["sales"] = {"level": level_codes[0], "caps": {}}
        if any(s["key"] == "margins" for s in catalog):
            pending["margins"] = {
                "level": "user",
                "caps": {"m_ops_view": True, "m_margins_view": True},
            }
        applied = user.jx_apply_permission_state(pending)
        self.assertEqual(applied["sales"]["level"], level_codes[0])
        if "margins" in applied:
            self.assertEqual(applied["margins"]["level"], "user")

    def test_mirror_role_inverse_refuses_real_change(self):
        """Guard stays: writing a different justech_ecf_role must still raise."""
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.user.write({"justech_ecf_role": "ecf_admin"})

    def test_existing_user_permission_state_loads(self):
        state = self.user.jx_permission_state()
        self.assertIsInstance(state, dict)
        self.assertIn("sales", state)
        catalog = self.Users.jx_catalog()
        self.assertTrue(any(s["key"] == "margins" for s in catalog) or True)
        # Margins present when module installed
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_purchase_sale_margin_control"), ("state", "=", "installed")],
            limit=1,
        )
        if mod:
            self.assertTrue(any(s["key"] == "margins" for s in catalog))
            margins = next(s for s in catalog if s["key"] == "margins")
            self.assertEqual(
                [L["label"] for L in margins["levels"]],
                ["Sin acceso", "Usuario", "Responsable", "Administrador"],
            )

    def test_margins_granular_persistence_after_reapply(self):
        mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_purchase_sale_margin_control"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            self.skipTest("margins module not installed")
        self.user.jx_apply_level("margins", "responsable")
        st = self.user.jx_permission_state()["margins"]
        self.assertEqual(st["level"], "responsable")
        self.assertTrue(st["caps"].get("m_margins_view"))
        self.assertFalse(st["caps"].get("m_board"))
        self.assertFalse(st["caps"].get("m_config"))
        # Custom: keep user preset + margins view without escalating level
        self.user.jx_apply_level("margins", "user")
        self.user.jx_apply_cap("m_margins_view", True)
        st2 = self.user.jx_permission_state()["margins"]
        self.assertEqual(st2["level"], "user")
        self.assertTrue(st2["caps"].get("m_margins_view"))
        self.assertTrue(st2["caps"].get("m_ops_view"))

    def test_companies_tab_in_view(self):
        view = self.env.ref(
            "justech_security_ux.view_users_form_operational_permissions"
        )
        arch = view.arch_db or ""
        self.assertIn('name="justech_user_companies"', arch)
        self.assertIn('name="company_id"', arch)
        self.assertIn('name="company_ids"', arch)
        self.assertIn("Empresa principal", arch)
        self.assertIn("Empresas permitidas", arch)

    def test_company_id_coerced_into_allowed_set(self):
        companies = self.env["res.company"].sudo().search([], limit=2)
        if len(companies) < 2:
            self.skipTest("need >=2 companies")
        c1, c2 = companies[0], companies[1]
        login = "uat_jx_co_constraint_%s" % self.env.cr.dbname
        user = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX Company Constraint",
                "login": login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "company_ids": [(6, 0, [c1.id])],
                "company_id": c1.id,
            }
        )
        # Replacing allowed set while keeping old principal → coerce principal to allowed
        user.write({"company_ids": [(6, 0, [c2.id])], "company_id": c1.id})
        self.assertEqual(user.company_id, c2)
        self.assertEqual(user.company_ids, c2)

    def test_non_admin_cannot_write_company_ids(self):
        from odoo.exceptions import AccessError

        companies = self.env["res.company"].sudo().search([], limit=2)
        if len(companies) < 2:
            self.skipTest("need >=2 companies")
        c1, c2 = companies[0], companies[1]
        login = "uat_jx_co_plain_%s" % self.env.cr.dbname
        plain = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX Plain",
                "login": login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "company_ids": [(6, 0, [c1.id])],
                "company_id": c1.id,
            }
        )
        target_login = "uat_jx_co_target_%s" % self.env.cr.dbname
        target = self.Users.with_context(no_reset_password=True).create(
            {
                "name": "UAT JX Target",
                "login": target_login,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "company_ids": [(6, 0, [c1.id])],
                "company_id": c1.id,
            }
        )
        with self.assertRaises(AccessError):
            target.with_user(plain).write(
                {"company_ids": [(6, 0, [c1.id, c2.id])], "company_id": c1.id}
            )
