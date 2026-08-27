# -*- coding: utf-8 -*-
"""19.0.8.27.0 — Usuario / Responsable / Administrador privilege matrix."""
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

MARGIN_GROUPS = (
    "justech_purchase_sale_margin_control.group_margin_readonly",
    "justech_purchase_sale_margin_control.group_margin_auditor",
    "justech_purchase_sale_margin_control.group_margin_sales",
    "justech_purchase_sale_margin_control.group_margin_purchase",
    "justech_purchase_sale_margin_control.group_margin_finance",
    "justech_purchase_sale_margin_control.group_margin_admin",
)


@tagged("post_install", "-at_install", "justech_margin", "justech_margin_access_827")
class TestMarginAccessControl827(TransactionCase):
    """Server-side access matrix for the simplified privilege levels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.no_access = new_test_user(
            cls.env,
            login="uat_margin_827_none",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls._strip_margin_groups(cls.no_access)

        cls.user_ro = new_test_user(
            cls.env,
            login="uat_margin_827_user",
            groups=(
                "justech_purchase_sale_margin_control.group_margin_readonly,"
                "base.group_user"
            ),
        )
        cls.user_mgr = new_test_user(
            cls.env,
            login="uat_margin_827_responsable",
            groups=(
                "justech_purchase_sale_margin_control.group_margin_finance,"
                "base.group_user"
            ),
        )
        cls.user_adm = new_test_user(
            cls.env,
            login="uat_margin_827_admin",
            groups=(
                "justech_purchase_sale_margin_control.group_margin_admin,"
                "base.group_user"
            ),
        )

        cls.root_menu = cls.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_root"
        )
        cls.config_menu = cls.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_config"
        )
        cls.tools_menu = cls.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_tools"
        )
        cls.priv = cls.env.ref(
            "justech_purchase_sale_margin_control.res_groups_privilege_margin_control"
        )
        cls.g_user = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_readonly"
        )
        cls.g_resp = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_finance"
        )
        cls.g_admin = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_admin"
        )
        cls.g_sales = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_sales"
        )
        cls.g_purchase = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_purchase"
        )
        cls.g_auditor = cls.env.ref(
            "justech_purchase_sale_margin_control.group_margin_auditor"
        )

    @classmethod
    def _strip_margin_groups(cls, user):
        for xmlid in MARGIN_GROUPS:
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group and group in user.group_ids:
                user.write({"group_ids": [(3, group.id)]})

    def _menus_for(self, user):
        return self.env["ir.ui.menu"].with_user(user).load_menus(False)

    def _menu_visible(self, user, menu):
        data = self._menus_for(user)
        return str(menu.id) in (data.get("root") or {}).get("children", []) or any(
            str(menu.id) == str(mid)
            for mid in self._flatten_menu_ids(data)
        )

    def _flatten_menu_ids(self, data):
        ids = set()

        def walk(node):
            if not isinstance(node, dict):
                return
            mid = node.get("id")
            if mid:
                ids.add(str(mid))
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    walk(child)
                else:
                    ids.add(str(child))
                    child_node = (data.get("menu_items") or {}).get(str(child)) or (
                        data.get("children") or {}
                    ).get(str(child))
                    if child_node:
                        walk(child_node)

        # Odoo 19 load_menus returns {root: {...}, ...} or nested structure
        if "root" in data:
            walk(data["root"])
        for key, val in data.items():
            if isinstance(val, dict) and key not in ("root",):
                walk(val)
        # Fallback: search all menus visible via _visible_menu_ids
        return ids

    def _has_menu(self, user, menu):
        Menu = self.env["ir.ui.menu"].with_user(user)
        visible = Menu._visible_menu_ids()
        return menu.id in visible

    def test_privilege_labels_and_membership(self):
        self.assertEqual(self.priv.name, "Control de Costos y Márgenes")
        self.assertEqual(self.g_user.name, "Usuario")
        self.assertEqual(self.g_resp.name, "Responsable")
        self.assertEqual(self.g_admin.name, "Administrador")
        self.assertEqual(self.g_user.privilege_id, self.priv)
        self.assertEqual(self.g_resp.privilege_id, self.priv)
        self.assertEqual(self.g_admin.privilege_id, self.priv)
        # Specialized roles stay for ACL but are not privilege options
        self.assertFalse(self.g_sales.privilege_id)
        self.assertFalse(self.g_purchase.privilege_id)
        self.assertFalse(self.g_auditor.privilege_id)

    def test_no_access_denied(self):
        self.assertFalse(self._has_menu(self.no_access, self.root_menu))
        MTX = self.env["purchase.sale.margin.transaction"].with_user(self.no_access)
        with self.assertRaises(AccessError):
            MTX.search([])
        with self.assertRaises(AccessError):
            MTX.search_read([], ["name"], limit=1)

    def test_usuario_read_only(self):
        self.assertTrue(self._has_menu(self.user_ro, self.root_menu))
        self.assertFalse(self._has_menu(self.user_ro, self.config_menu))
        self.assertFalse(self._has_menu(self.user_ro, self.tools_menu))
        MTX = self.env["purchase.sale.margin.transaction"].with_user(self.user_ro)
        MTX.search([])  # read OK
        with self.assertRaises(AccessError):
            MTX.check_access("create")
        with self.assertRaises(AccessError):
            MTX.check_access("write")

    def test_responsable_ops_no_config(self):
        self.assertTrue(self._has_menu(self.user_mgr, self.root_menu))
        self.assertTrue(self._has_menu(self.user_mgr, self.tools_menu))
        self.assertFalse(self._has_menu(self.user_mgr, self.config_menu))
        MTX = self.env["purchase.sale.margin.transaction"].with_user(self.user_mgr)
        MTX.check_access("write")

    def test_administrador_full(self):
        self.assertTrue(self._has_menu(self.user_adm, self.root_menu))
        self.assertTrue(self._has_menu(self.user_adm, self.tools_menu))
        self.assertTrue(self._has_menu(self.user_adm, self.config_menu))
        Rule = self.env["purchase.sale.reconciliation.rule"].with_user(self.user_adm)
        Rule.check_access("write")

    def test_system_admin_implies_margin_admin(self):
        admin = self.env.ref("base.user_admin")
        self.assertTrue(
            admin.has_group("justech_purchase_sale_margin_control.group_margin_admin")
        )

    def test_multi_company_rule_present(self):
        rule = self.env.ref(
            "justech_purchase_sale_margin_control.rule_margin_transaction_multi_company"
        )
        self.assertIn("company_ids", rule.domain_force)
