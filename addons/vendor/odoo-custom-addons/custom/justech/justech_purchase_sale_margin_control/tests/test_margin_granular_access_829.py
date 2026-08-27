# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "justech_margins_granular")
class TestMarginsGranularAccess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].with_user(self.env.ref("base.user_admin"))
        self.user = self.Users.create(
            {
                "name": "UAT Margins Granular",
                "login": "uat_margins_granular_%s" % self.env.cr.dbname,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.Menu = self.env["ir.ui.menu"]
        self.root = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_root"
        )
        self.board = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_board"
        )
        self.ops = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_transaction"
        )
        self.margins = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margins"
        )
        self.cxp = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_payable_auxiliary_root"
        )
        self.config = self.env.ref(
            "justech_purchase_sale_margin_control.menu_purchase_sale_margin_config"
        )

    def _visible(self, menu):
        return menu.id in self.Menu.with_user(self.user)._visible_menu_ids()

    def test_catalog_has_section_caps(self):
        catalog = self.Users.jx_catalog()
        margins = next(s for s in catalog if s["key"] == "margins")
        self.assertEqual(margins.get("caps_title"), "Acceso a secciones")
        codes = {c["code"] for c in margins["caps"]}
        for code in (
            "m_board",
            "m_inbox",
            "m_ops_view",
            "m_ops_manage",
            "m_margins_view",
            "m_margins_manage",
            "m_cxp_view",
            "m_cxp_manage",
            "m_reports_view",
            "m_reports_export",
            "m_config",
        ):
            self.assertIn(code, codes)

    def test_user_preset_ops_only(self):
        self.user.jx_apply_level("margins", "user")
        self.assertTrue(self._visible(self.root))
        self.assertTrue(self._visible(self.ops))
        self.assertFalse(self._visible(self.board))
        self.assertFalse(self._visible(self.margins))
        self.assertFalse(self._visible(self.cxp))
        self.assertFalse(self._visible(self.config))
        # RPC: transaction search OK; board AccessError
        self.env(user=self.user)["purchase.sale.margin.transaction"].search([], limit=1)
        with self.assertRaises(AccessError):
            self.env(user=self.user)["purchase.sale.margin.board"].check_access("read")

    def test_ops_without_margins_hides_sensitive_fields(self):
        self.user.jx_apply_level("margins", "none")
        self.user.jx_apply_level("margins", "user")
        # ensure only ops view (user preset)
        self.assertFalse(
            self.user.has_group(
                "justech_purchase_sale_margin_control.group_margin_sec_margins_view"
            )
        )
        fields = self.env(user=self.user)["purchase.sale.margin.transaction"].fields_get(
            ["display_margin_amount", "name", "state"]
        )
        self.assertIn("name", fields)
        self.assertNotIn("display_margin_amount", fields)

    def test_responsable_no_board_cxp_config(self):
        self.user.jx_apply_level("margins", "responsable")
        self.assertTrue(self._visible(self.ops))
        self.assertTrue(self._visible(self.margins))
        self.assertFalse(self._visible(self.board))
        self.assertFalse(self._visible(self.cxp))
        self.assertFalse(self._visible(self.config))
        self.assertFalse(
            self.user.has_group("base.group_system")
            or self.user.has_group("account.group_account_manager")
        )

    def test_admin_all_sections(self):
        self.user.jx_apply_level("margins", "admin")
        for menu in (self.root, self.board, self.ops, self.margins, self.cxp, self.config):
            self.assertTrue(self._visible(menu), menu.complete_name)

    def test_none_clears(self):
        self.user.jx_apply_level("margins", "admin")
        self.user.jx_apply_level("margins", "none")
        self.assertFalse(self._visible(self.root))
        with self.assertRaises(AccessError):
            self.env(user=self.user)["purchase.sale.margin.transaction"].search([], limit=1)
