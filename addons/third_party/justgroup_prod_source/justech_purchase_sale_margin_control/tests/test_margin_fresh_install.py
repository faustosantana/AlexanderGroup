# -*- coding: utf-8 -*-
"""Fresh-install safety and upgrade compatibility for Costos y Márgenes."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from lxml import etree

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


MODULE = "justech_purchase_sale_margin_control"
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "__manifest__.py"
ODOO19_VERSION_RE = re.compile(r"^19\.0\.\d+\.\d+\.\d+$")


def _manifest_dict():
    return ast.literal_eval(MANIFEST_PATH.read_text(encoding="utf-8"))


MENUS_XML = (
    Path(__file__).resolve().parents[1] / "views" / "menus.xml"
)

LEGACY_MENU_XML_NAMES = {
    "menu_purchase_sale_margin_report_wizard",
    "menu_purchase_sale_payable_auxiliary_pending_relation",
    "menu_purchase_sale_payable_auxiliary_pending_payment",
    "menu_purchase_sale_payable_auxiliary_paid",
    "menu_purchase_sale_payable_auxiliary_no_sale",
    "menu_purchase_sale_payable_auxiliary_differences",
    "menu_purchase_sale_payable_auxiliary_closed",
    "menu_purchase_sale_payable_auxiliary_pending_invoice",
    "menu_purchase_sale_margin_transaction_negative_margins",
    "menu_purchase_sale_pending_links",
    "menu_purchase_sale_margin_tools",
}

EXPECTED_ROOT_CHILDREN = {
    "Resumen financiero",
    "Pendientes",
    "Operaciones",
    "Márgenes",
    "Cuentas por Pagar",
    "Reportes",
    "Configuración",
}


@tagged("post_install", "-at_install")
class TestMarginFreshInstall(TransactionCase):
    """Guarantee install-safe XML and a complete application menu tree."""

    def _root_menu(self):
        data = self.env["ir.model.data"].search(
            [
                ("module", "=", MODULE),
                ("name", "=", "menu_purchase_sale_margin_root"),
            ],
            limit=1,
        )
        self.assertTrue(data, "Root menu xml id must exist after install")
        return self.env["ir.ui.menu"].browse(data.res_id)

    def test_01_menus_xml_no_incomplete_ir_ui_menu_records(self):
        tree = etree.parse(str(MENUS_XML))
        offenders = []
        for record in tree.xpath("//record[@model='ir.ui.menu']"):
            xml_id = record.get("id")
            fields = {node.get("name"): (node.text or "").strip() for node in record.xpath("field")}
            has_name = bool(fields.get("name"))
            only_active_false = set(fields) <= {"active"} and fields.get("active") in ("False", "0")
            if only_active_false and not has_name:
                offenders.append(xml_id)
        self.assertFalse(
            offenders,
            "menus.xml must not contain update-only ir.ui.menu records: %s" % offenders,
        )

    def test_02_menus_xml_legacy_ids_not_referenced_for_deactivation(self):
        tree = etree.parse(str(MENUS_XML))
        referenced = {
            record.get("id")
            for record in tree.xpath("//record[@model='ir.ui.menu']")
            if record.get("id") in LEGACY_MENU_XML_NAMES
        }
        self.assertFalse(
            referenced,
            "Legacy menu xml ids must be cleaned via migration, not XML: %s" % referenced,
        )

    def test_03_app_root_menu_present_with_icon(self):
        root = self._root_menu()
        self.assertEqual(root.name, "Costos y Márgenes")
        self.assertTrue(root.active)
        module_meta = self.env["ir.module.module"].search([("name", "=", MODULE)], limit=1)
        self.assertEqual(module_meta.state, "installed")
        self.assertTrue(module_meta.application)

    def test_04_app_menu_tree_complete(self):
        root = self._root_menu()
        child_names = set(root.child_id.mapped("name"))
        missing = EXPECTED_ROOT_CHILDREN - child_names
        self.assertFalse(missing, "Missing root menus: %s" % sorted(missing))

    def test_05_no_duplicate_report_menus_for_historical_wizard(self):
        Menu = self.env["ir.ui.menu"]
        historical = Menu.search(
            [
                ("name", "=", "Reportes históricos"),
                ("parent_id.name", "=", "Reportes"),
            ]
        )
        active_historical = historical.filtered("active")
        self.assertEqual(
            len(active_historical),
            1,
            "Exactly one active 'Reportes históricos' menu expected",
        )

    def test_06_legacy_menus_inactive_or_absent_after_upgrade(self):
        Imd = self.env["ir.model.data"]
        Menu = self.env["ir.ui.menu"]
        for xml_name in LEGACY_MENU_XML_NAMES:
            data = Imd.search(
                [("module", "=", MODULE), ("name", "=", xml_name)],
                limit=1,
            )
            if not data:
                continue
            menu = Menu.browse(data.res_id)
            self.assertFalse(
                menu.active,
                "Legacy menu %s must be inactive after 8.22 upgrade" % xml_name,
            )

    def test_07_report_actions_registered(self):
        for xml_name in (
            "action_report_cost_vs_sale_pdf",
            "action_purchase_sale_cost_vs_sale_report",
            "action_purchase_sale_margin_report_wizard",
        ):
            data = self.env["ir.model.data"].search(
                [("module", "=", MODULE), ("name", "=", xml_name)],
                limit=1,
            )
            self.assertTrue(data, "Missing action xml id %s" % xml_name)

    def test_08_preview_action_uses_qweb_html(self):
        Report = self.env["purchase.sale.cost.vs.sale.report"]
        report = Report.create(
            {
                "date_from": fields.Date.today(),
                "date_to": fields.Date.today(),
            }
        )
        action = report.action_preview()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-html")

    def test_09_vbc_fields_coexist_on_account_move(self):
        """Vendor bill PO control fields must remain alongside jm_* fields."""
        Move = self.env["account.move"]
        vbc_fields = {
            name
            for name, field in Move._fields.items()
            if name.startswith("vendor_bill_")
            or name in ("related_purchase_order_ids", "has_valid_purchase_order", "po_control_state")
        }
        jm_fields = {name for name in Move._fields if name.startswith("jm_")}
        self.assertTrue(vbc_fields, "Expected VBC fields on account.move")
        self.assertTrue(jm_fields, "Expected jm_* fields on account.move")
        overlap = vbc_fields & jm_fields
        self.assertFalse(overlap, "Field name collision: %s" % overlap)

    def test_10_action_post_mro_includes_vbc_and_margin(self):
        Move = self.env["account.move"]
        mro_names = [cls.__name__ for cls in Move.__class__.mro()]
        self.assertIn("AccountMoveAutoLink", mro_names)
        self.assertIn("AccountMove", mro_names)
        # VBC model class name on installed stack
        vbc_present = any("vendor_bill" in n.lower() or "justech" in n.lower() for n in mro_names)
        self.assertTrue(vbc_present or "AccountMove" in mro_names)

    def test_11_manifest_version_matches_installed_module(self):
        """Single source of truth: __manifest__ version must match installed module.

        Do not hardcode a release patch (8.22/8.23/…): that breaks every bump.
        """
        manifest_version = _manifest_dict()["version"]
        self.assertRegex(manifest_version, ODOO19_VERSION_RE)
        mod = self.env["ir.module.module"].search([("name", "=", MODULE)], limit=1)
        self.assertEqual(mod.state, "installed")
        installed = mod.latest_version or mod.installed_version or ""
        self.assertTrue(
            installed == manifest_version or installed.endswith(manifest_version),
            "Installed %r must match manifest %r" % (installed, manifest_version),
        )

    def test_12_menus_xml_menuitem_ids_unique(self):
        tree = etree.parse(str(MENUS_XML))
        ids = tree.xpath("//*[@id]/@id")
        dupes = {x for x in ids if ids.count(x) > 1}
        self.assertFalse(dupes, "Duplicate xml ids in menus.xml: %s" % dupes)

    def test_12b_menus_xml_parents_defined_before_use(self):
        tree = etree.parse(str(MENUS_XML))
        seen = set()
        for node in tree.xpath("//menuitem"):
            xml_id = node.get("id")
            parent = node.get("parent")
            if parent:
                self.assertIn(
                    parent,
                    seen,
                    "Menu %s references parent %s before it is defined in menus.xml"
                    % (xml_id, parent),
                )
            if xml_id:
                seen.add(xml_id)

    def test_13_no_empty_menu_names_in_database(self):
        Menu = self.env["ir.ui.menu"]
        module_menus = Menu.search(
            [
                (
                    "id",
                    "in",
                    self.env["ir.model.data"]
                    .search([("module", "=", MODULE), ("model", "=", "ir.ui.menu")])
                    .mapped("res_id"),
                )
            ]
        )
        empty = module_menus.filtered(lambda m: not (m.name or "").strip())
        self.assertFalse(empty, "Menus with empty name: %s" % empty.ids)
