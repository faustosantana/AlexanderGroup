# -*- coding: utf-8 -*-
"""Post-init / migrate helpers for UX consolidation with Trace (optional)."""
import json
import logging

from lxml import etree

_logger = logging.getLogger(__name__)

TRACE_INVOICE_BTN_NAMES = (
    "action_justech_invoice_buy_pending",
    "action_justech_invoice_link_existing_po",
)

# Cotización / SO: hide Trace purchase UX; margins hub is the only entry.
TRACE_SO_BTN_NAMES = (
    "action_justech_buy_pending",
    "action_justech_link_existing_po",
)

# Hide Trace supply columns from normal SO line grid (hub holds coverage UX).
TRACE_SO_LINE_COLUMN_FIELDS = (
    "justech_qty_stock_covered",
    "justech_qty_purchased",
    "justech_qty_pending_purchase",
    "justech_qty_received",
    "justech_qty_pending_receive",
    "justech_qty_pending_deliver",
    "justech_supply_state",
    "justech_coverage_state",
)


def redirect_trace_invoice_purchase_actions(env):
    """Point Trace invoice purchase entrypoints at Gestionar compras hub."""
    try:
        Model = env.registry["account.move"]
    except KeyError:
        return
    if not hasattr(Model, "action_manage_purchases"):
        return

    def _hub(self):
        return self.action_manage_purchases()

    for name in TRACE_INVOICE_BTN_NAMES:
        if hasattr(Model, name):
            setattr(Model, name, _hub)
            _logger.info("Redirected account.move.%s → action_manage_purchases", name)


def redirect_trace_sale_purchase_actions(env):
    """Redirect Trace SO «Relacionar compra existente» to Gestionar compras hub.

    Keep ``action_justech_buy_pending`` callable for the hub's «Crear orden de
    compra» path (button is hidden only).
    """
    try:
        Model = env.registry["sale.order"]
    except KeyError:
        return
    if not hasattr(Model, "action_manage_purchases"):
        return

    def _hub(self):
        return self.action_manage_purchases()

    if hasattr(Model, "action_justech_link_existing_po"):
        setattr(Model, "action_justech_link_existing_po", _hub)
        _logger.info(
            "Redirected sale.order.action_justech_link_existing_po → action_manage_purchases"
        )


def _set_buttons_invisible(arch_str, button_names):
    if not arch_str:
        return arch_str, False
    wrapped = False
    raw = arch_str
    try:
        root = etree.fromstring(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except etree.XMLSyntaxError:
        try:
            root = etree.fromstring(
                ("<data>%s</data>" % raw).encode("utf-8")
            )
            wrapped = True
        except etree.XMLSyntaxError:
            return arch_str, False
    changed = False
    for name in button_names:
        for btn in root.xpath("//button[@name='%s']" % name):
            if btn.get("invisible") != "1":
                btn.set("invisible", "1")
                changed = True
    if not changed:
        return arch_str, False
    out = etree.tostring(root, encoding="unicode")
    if wrapped and out.startswith("<data>") and out.endswith("</data>"):
        out = out[len("<data>") : -len("</data>")]
    return out, True


def _set_list_fields_column_invisible(arch_str, field_names):
    if not arch_str:
        return arch_str, False
    wrapped = False
    raw = arch_str
    try:
        root = etree.fromstring(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except etree.XMLSyntaxError:
        try:
            root = etree.fromstring(
                ("<data>%s</data>" % raw).encode("utf-8")
            )
            wrapped = True
        except etree.XMLSyntaxError:
            return arch_str, False
    changed = False
    for name in field_names:
        for field in root.xpath("//field[@name='%s']" % name):
            if field.get("column_invisible") != "1":
                field.set("column_invisible", "1")
                changed = True
            if field.get("optional") == "show":
                field.set("optional", "hide")
                changed = True
    if not changed:
        return arch_str, False
    out = etree.tostring(root, encoding="unicode")
    if wrapped and out.startswith("<data>") and out.endswith("</data>"):
        out = out[len("<data>") : -len("</data>")]
    return out, True


def _patch_trace_view_arch(env, xmlid, label, mutator):
    parent = env.ref(xmlid, raise_if_not_found=False)
    if not parent:
        return False
    env.cr.execute("SELECT arch_db FROM ir_ui_view WHERE id=%s", (parent.id,))
    row = env.cr.fetchone()
    if not row or row[0] is None:
        return False
    current = row[0]
    any_changed = False
    if isinstance(current, dict):
        new_map = {}
        for lang, xml in current.items():
            new_xml, changed = mutator(xml)
            new_map[lang] = new_xml
            any_changed = any_changed or changed
        if not any_changed:
            return False
        env.cr.execute(
            "UPDATE ir_ui_view SET arch_db=%s::jsonb WHERE id=%s",
            (json.dumps(new_map), parent.id),
        )
    elif isinstance(current, str):
        try:
            parsed = json.loads(current)
            if isinstance(parsed, dict):
                for lang, xml in parsed.items():
                    parsed[lang], ch = mutator(xml)
                    any_changed = any_changed or ch
                if not any_changed:
                    return False
                env.cr.execute(
                    "UPDATE ir_ui_view SET arch_db=%s::jsonb WHERE id=%s",
                    (json.dumps(parsed), parent.id),
                )
            else:
                new_xml, changed = mutator(current)
                if not changed:
                    return False
                env.cr.execute(
                    "UPDATE ir_ui_view SET arch_db=%s WHERE id=%s",
                    (new_xml, parent.id),
                )
                any_changed = True
        except json.JSONDecodeError:
            new_xml, changed = mutator(current)
            if not changed:
                return False
            env.cr.execute(
                "UPDATE ir_ui_view SET arch_db=%s WHERE id=%s",
                (new_xml, parent.id),
            )
            any_changed = True
    else:
        return False
    env.invalidate_all()
    _logger.info("Patched Trace %s view %s", label, parent.id)
    return True


def _hide_trace_view_buttons(env, xmlid, button_names, label):
    return _patch_trace_view_arch(
        env,
        xmlid,
        label,
        lambda xml: _set_buttons_invisible(xml, button_names),
    )


def ensure_trace_invoice_buttons_hidden(env):
    return _hide_trace_view_buttons(
        env,
        "justech_sale_purchase_trace.view_account_move_form_justech_trace",
        TRACE_INVOICE_BTN_NAMES,
        "invoice",
    )


def ensure_trace_sale_buttons_hidden(env):
    return _hide_trace_view_buttons(
        env,
        "justech_sale_purchase_trace.view_sale_order_form_justech_trace",
        TRACE_SO_BTN_NAMES,
        "sale.order",
    )


def ensure_trace_so_supply_columns_hidden(env):
    """Hide Trace supply columns on SO order_line list (hub owns coverage UX)."""
    return _patch_trace_view_arch(
        env,
        "justech_sale_purchase_trace.view_sale_order_form_justech_trace",
        "sale.order supply columns",
        lambda xml: _set_list_fields_column_invisible(xml, TRACE_SO_LINE_COLUMN_FIELDS),
    )


def ensure_margin_menu_groups_synced(env):
    """Align menu group_ids with menus.xml functional groups (drop stale section-only leftovers)."""
    MODULE = "justech_purchase_sale_margin_control"
    MENU_GROUPS = {
        "menu_purchase_sale_margin_root": ("group_margin_readonly",),
        "menu_purchase_sale_margin_board": ("group_margin_readonly",),
        "menu_purchase_sale_work_inbox": ("group_margin_readonly",),
        "menu_purchase_sale_unrelated_docs": ("group_margin_readonly",),
        "menu_purchase_sale_margin_transaction_pending_validation": ("group_margin_finance",),
        "menu_purchase_sale_margin_transaction_pending_approval": ("group_margin_finance",),
        "menu_purchase_sale_margin_transaction_purchases_without_sale": ("group_margin_readonly",),
        "menu_purchase_sale_margin_transaction_sales_without_cost": ("group_margin_readonly",),
        "menu_purchase_sale_margin_transaction_admin_expenses": ("group_margin_finance",),
        "menu_purchase_sale_margin_transaction": ("group_margin_readonly",),
        "menu_purchase_sale_margins": ("group_margin_readonly",),
        "menu_purchase_sale_payable_auxiliary_root": ("group_margin_readonly",),
        "menu_purchase_sale_margin_reports": ("group_margin_readonly",),
        "menu_purchase_sale_margin_historical_reports": ("group_margin_readonly",),
        "menu_purchase_sale_cost_vs_sale_report": ("group_margin_readonly",),
        "menu_purchase_sale_payable_auxiliary_report": ("group_margin_finance",),
        "menu_purchase_sale_margin_snapshot": ("group_margin_readonly",),
        "menu_purchase_sale_margin_tools": ("group_margin_finance",),
        "menu_purchase_sale_relate_documents_wizard": ("group_margin_finance",),
        "menu_purchase_sale_create_transaction_wizard": ("group_margin_finance",),
        "menu_purchase_sale_register_cost_wizard": ("group_margin_finance",),
        "menu_purchase_sale_register_sale_wizard": ("group_margin_finance",),
        "menu_purchase_sale_allocate_wizard": ("group_margin_finance",),
        "menu_purchase_sale_prorate_wizard": ("group_margin_finance",),
        "menu_purchase_sale_add_purchase_wizard": ("group_margin_finance",),
        "menu_purchase_sale_relate_sale_wizard": ("group_margin_finance",),
        "menu_purchase_sale_margin_config": ("group_margin_admin",),
        "menu_purchase_sale_reconciliation_rule": ("group_margin_admin",),
        "menu_purchase_sale_cost_link": ("group_margin_admin",),
        "menu_purchase_sale_cost_allocation": ("group_margin_admin",),
        "menu_purchase_sale_backfill_wizard": ("group_margin_admin",),
        "menu_purchase_sale_margin_uat_wizard": ("group_margin_admin",),
        "menu_purchase_sale_margin_uat_cleanup_wizard": ("group_margin_admin",),
    }
    Menu = env["ir.ui.menu"]
    gf = "group_ids" if "group_ids" in Menu._fields else "groups_id"
    synced = 0
    for menu_xml, group_xmls in MENU_GROUPS.items():
        menu = env.ref(f"{MODULE}.{menu_xml}", raise_if_not_found=False)
        if not menu:
            continue
        group_ids = []
        for gxml in group_xmls:
            group = env.ref(f"{MODULE}.{gxml}", raise_if_not_found=False)
            if group:
                group_ids.append(group.id)
        if group_ids:
            menu.write({gf: [(6, 0, group_ids)]})
            synced += 1
    env.invalidate_all()
    _logger.info("Synced margin menu groups (%s menus)", synced)
    return synced


def ensure_margin_app_menu_restored(env):
    """Ensure Costos y Márgenes root opens dashboard (app switcher visibility)."""
    root = env.ref(
        "justech_purchase_sale_margin_control.menu_purchase_sale_margin_root",
        raise_if_not_found=False,
    )
    board = env.ref(
        "justech_purchase_sale_margin_control.action_purchase_sale_margin_board",
        raise_if_not_found=False,
    )
    if not root or not board:
        return False
    ro = env.ref("justech_purchase_sale_margin_control.group_margin_readonly")
    gf = "group_ids" if "group_ids" in root._fields else "groups_id"
    updates = {}
    if not root.action:
        updates["action"] = board.id
    if not root.active:
        updates["active"] = True
    if updates:
        root.write(updates)
    root.write({gf: [(6, 0, [ro.id])]})
    board.write({"group_ids": [(6, 0, [ro.id])]})
    env.invalidate_all()
    _logger.info("Restored margin app root menu action=%s", board.id)
    return True
