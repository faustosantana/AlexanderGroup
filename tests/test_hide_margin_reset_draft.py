"""Doralex: hide Costos y Márgenes; restore Reset to draft."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UX = REPO / "addons" / "alexander" / "justech_alexander_ux"
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_margin_app_is_not_visible():
    hooks = (UX / "hooks.py").read_text(encoding="utf-8")
    menus = (UX / "views" / "menus.xml").read_text(encoding="utf-8")
    manifest = (UX / "__manifest__.py").read_text(encoding="utf-8")
    visible = hooks.split("VISIBLE_APPS", 1)[1].split("}", 1)[0]
    assert "justech_purchase_sale_margin_control" not in visible
    assert (
        '("justech_purchase_sale_margin_control", "Costos y Márgenes", False)' in hooks
    )
    assert (
        '("justech_purchase_sale_margin_control", "Costos y Márgenes", True)'
        not in hooks
    )
    assert "hide_margin_control" in hooks
    assert "menu_purchase_sale_margin_root" in menus
    assert 'name="active" eval="False"' in menus
    assert "justech_purchase_sale_margin_control" in manifest
    assert "19.0.1.6.11" in manifest


def test_invoice_and_sale_hide_margin_ui():
    invoice = (UX / "views" / "account_move_views.xml").read_text(encoding="utf-8")
    sale = (UX / "views" / "sale_order_views.xml").read_text(encoding="utf-8")
    assert "margin_out_panel" in invoice
    assert "action_manage_purchases" in invoice
    assert "justech_margin_cxp" in invoice
    assert "margin_control_compact" in sale
    assert "<delete" not in invoice
    assert "<delete" not in sale


def test_reset_to_draft_uses_invoicing_not_recovery():
    source = (BASE / "models" / "account_move_draft.py").read_text(encoding="utf-8")
    views = (BASE / "views" / "account_move_views.xml").read_text(encoding="utf-8")
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    assert "def button_draft" in source
    assert "account.group_account_invoice" in source
    assert "justech_accounting_recovery.models.account_move" in source
    assert 'string="Restablecer a borrador"' in views
    assert 'name="button_draft"' in views
    assert "19.0.1.0.24" in manifest
