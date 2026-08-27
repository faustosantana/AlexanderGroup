# -*- coding: utf-8 -*-
"""Regression guardrails for 19.0.8.29.35 stabilization."""
from __future__ import annotations

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MODULE = "justech_purchase_sale_margin_control"

REPORT_MENUS = (
    "menu_purchase_sale_cost_vs_sale_report",
    "menu_purchase_sale_payable_auxiliary_report",
    "menu_purchase_sale_margin_historical_reports",
    "menu_purchase_sale_margin_snapshot",
)

REPORT_MODELS = (
    "purchase.sale.cost.vs.sale.report",
    "purchase.sale.payable.auxiliary.report",
    "purchase.sale.margin.report.wizard",
    "purchase.sale.margin.snapshot",
)


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginStabilization2935(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ro = cls.env.ref(f"{MODULE}.group_margin_readonly")
        cls.fin = cls.env.ref(f"{MODULE}.group_margin_finance")
        cls.readonly_user = cls.env["res.users"].create(
            {
                "name": "UAT Margin Readonly 2935",
                "login": "uat_margin_readonly_2935",
                "group_ids": [(6, 0, [cls.ro.id])],
            }
        )
        cls.finance_user = cls.env["res.users"].create(
            {
                "name": "UAT Margin Finance 2935",
                "login": "uat_margin_finance_2935",
                "group_ids": [(6, 0, [cls.fin.id])],
            }
        )

    def test_readonly_implies_report_section_cap(self):
        sec = self.env.ref(f"{MODULE}.group_margin_sec_reports_view")
        self.assertIn(sec, self.ro.implied_ids)

    def test_finance_implies_report_export_cap(self):
        sec = self.env.ref(f"{MODULE}.group_margin_sec_reports_export")
        self.assertIn(sec, self.fin.implied_ids)

    def test_report_menus_use_functional_groups_only(self):
        sec_view = self.env.ref(f"{MODULE}.group_margin_sec_reports_view")
        sec_export = self.env.ref(f"{MODULE}.group_margin_sec_reports_export")
        for xmlid in REPORT_MENUS:
            menu = self.env.ref(f"{MODULE}.{xmlid}")
            self.assertTrue(menu.active)
            sec_groups = menu.group_ids & (sec_view | sec_export)
            self.assertFalse(
                sec_groups,
                "Menu %s must not require section-only groups: %s"
                % (xmlid, sec_groups.mapped("name")),
            )

    def test_reports_parent_has_four_children(self):
        parent = self.env.ref(f"{MODULE}.menu_purchase_sale_margin_reports")
        names = set(parent.child_id.filtered("active").mapped("name"))
        self.assertTrue(
            {
                "Detalle de Costos vs Ventas",
                "Cuentas por Pagar",
                "Reportes históricos",
                "Fotos de margen (histórico)",
            }.issubset(names)
        )

    def test_readonly_user_can_read_view_reports(self):
        today = fields.Date.today()
        models_vals = {
            "purchase.sale.cost.vs.sale.report": {
                "date_from": today,
                "date_to": today,
            },
            "purchase.sale.payable.auxiliary.report": {},
            "purchase.sale.margin.report.wizard": {
                "date_from": today,
                "date_to": today,
            },
        }
        env_u = self.env(user=self.readonly_user)
        for model, vals in models_vals.items():
            rec = env_u[model].create(vals)
            rec.check_access("read")

    def test_finance_user_can_read_export_reports(self):
        env_u = self.env(user=self.finance_user)
        env_u["purchase.sale.payable.auxiliary.report"].check_access("read")
        env_u["purchase.sale.payable.auxiliary.report"].check_access("write")

    def test_readonly_user_cannot_write_cost_vs_sale_report(self):
        today = fields.Date.today()
        rec = self.env["purchase.sale.cost.vs.sale.report"].create(
            {"date_from": today, "date_to": today}
        )
        with self.assertRaises(AccessError):
            rec.with_user(self.readonly_user).write({"date_to": today})

    def test_root_menu_tree_includes_reportes(self):
        root = self.env.ref(f"{MODULE}.menu_purchase_sale_margin_root")
        self.assertIn("Reportes", root.child_id.mapped("name"))

    def test_report_actions_resolve(self):
        for xmlid in (
            "action_purchase_sale_cost_vs_sale_report",
            "action_purchase_sale_payable_auxiliary_report",
            "action_purchase_sale_margin_report_wizard",
            "action_purchase_sale_margin_snapshot",
        ):
            action = self.env.ref(f"{MODULE}.{xmlid}")
            self.assertTrue(action)
