# -*- coding: utf-8 -*-
"""Force menu group_ids to section ACL groups only (drop legacy ladder leftovers)."""

from odoo import api, SUPERUSER_ID

MODULE = "justech_purchase_sale_margin_control"

# xmlid menu -> xmlid groups (exact replace)
MENU_GROUPS = {
    "menu_purchase_sale_margin_root": ("group_margin_readonly",),
    "menu_purchase_sale_margin_board": ("group_margin_sec_board",),
    "menu_purchase_sale_work_inbox": ("group_margin_sec_inbox",),
    "menu_purchase_sale_unrelated_docs": ("group_margin_sec_inbox",),
    "menu_purchase_sale_margin_transaction_pending_validation": (
        "group_margin_sec_inbox",
        "group_margin_sec_ops_manage",
    ),
    "menu_purchase_sale_margin_transaction_pending_approval": (
        "group_margin_sec_inbox",
        "group_margin_sec_board",
    ),
    "menu_purchase_sale_margin_transaction_purchases_without_sale": ("group_margin_sec_inbox",),
    "menu_purchase_sale_margin_transaction_sales_without_cost": ("group_margin_sec_inbox",),
    "menu_purchase_sale_margin_transaction_admin_expenses": (
        "group_margin_sec_inbox",
        "group_margin_sec_board",
    ),
    "menu_purchase_sale_margin_transaction": ("group_margin_sec_ops_view",),
    "menu_purchase_sale_margins": ("group_margin_sec_margins_view",),
    "menu_purchase_sale_payable_auxiliary_root": ("group_margin_sec_cxp_view",),
    "menu_purchase_sale_margin_reports": ("group_margin_sec_reports_view",),
    "menu_purchase_sale_margin_historical_reports": ("group_margin_sec_reports_view",),
    "menu_purchase_sale_cost_vs_sale_report": ("group_margin_sec_reports_view",),
    "menu_purchase_sale_payable_auxiliary_report": ("group_margin_sec_reports_export",),
    "menu_purchase_sale_margin_snapshot": ("group_margin_sec_reports_view",),
    "menu_purchase_sale_margin_tools": ("group_margin_sec_ops_manage",),
    "menu_purchase_sale_relate_documents_wizard": ("group_margin_sec_ops_manage",),
    "menu_purchase_sale_create_transaction_wizard": ("group_margin_sec_ops_manage",),
    "menu_purchase_sale_register_cost_wizard": (
        "group_margin_sec_ops_manage",
        "group_margin_sec_margins_manage",
    ),
    "menu_purchase_sale_register_sale_wizard": ("group_margin_sec_ops_manage",),
    "menu_purchase_sale_allocate_wizard": (
        "group_margin_sec_ops_manage",
        "group_margin_sec_margins_manage",
    ),
    "menu_purchase_sale_prorate_wizard": (
        "group_margin_sec_ops_manage",
        "group_margin_sec_margins_manage",
    ),
    "menu_purchase_sale_add_purchase_wizard": ("group_margin_sec_ops_manage",),
    "menu_purchase_sale_relate_sale_wizard": (
        "group_margin_sec_ops_manage",
        "group_margin_sec_cxp_manage",
    ),
    "menu_purchase_sale_margin_config": ("group_margin_sec_config",),
    "menu_purchase_sale_reconciliation_rule": ("group_margin_sec_config",),
    "menu_purchase_sale_cost_link": ("group_margin_sec_config",),
    "menu_purchase_sale_cost_allocation": ("group_margin_sec_config",),
    "menu_purchase_sale_backfill_wizard": ("group_margin_sec_config",),
    "menu_purchase_sale_margin_uat_wizard": ("group_margin_sec_config",),
    "menu_purchase_sale_margin_uat_cleanup_wizard": ("group_margin_sec_config",),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env["ir.ui.menu"]
    for menu_xml, group_xmls in MENU_GROUPS.items():
        menu = env.ref(f"{MODULE}.{menu_xml}", raise_if_not_found=False)
        if not menu:
            continue
        group_ids = []
        for gxml in group_xmls:
            group = env.ref(f"{MODULE}.{gxml}", raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        # Odoo 19: group_ids (was groups_id)
        field = "group_ids" if "group_ids" in Menu._fields else "groups_id"
        menu.write({field: [(6, 0, group_ids)]})
