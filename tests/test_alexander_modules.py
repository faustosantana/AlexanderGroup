"""Pruebas de módulos overlay justech_alexander_*."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALEXANDER = REPO_ROOT / "addons" / "alexander"

EXPECTED = {
    "justech_alexander_base",
    "justech_alexander_website",
    "justech_alexander_admin",
    "justech_alexander_reports",
    "justech_alexander_microsoft_mail",
    "justech_alexander_ux",
}

CONFIDENTIAL_MARKERS = (
    "1-32-",
    "1-33-",
    "cedula",
    "cédula",
    "representante legal",
    "acc_number",
    "partner.comment",
    "company.vat",
)


def _manifests() -> list[Path]:
    return list(ALEXANDER.rglob("__manifest__.py"))


def test_alexander_modules_present() -> None:
    names = {path.parent.name for path in _manifests()}
    assert EXPECTED <= names


def test_shared_has_no_own_modules() -> None:
    own = list((REPO_ROOT / "addons" / "shared").rglob("__manifest__.py"))
    assert not own


def test_website_templates_hide_confidential_data() -> None:
    website = ALEXANDER / "justech_alexander_website"
    files = list(website.rglob("*.xml")) + list(website.rglob("*.py"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for marker in CONFIDENTIAL_MARKERS:
            assert marker not in text, f"{marker} en {path}"


def test_public_logo_uses_dedicated_route() -> None:
    payload = (
        ALEXANDER / "justech_alexander_base" / "models" / "res_company.py"
    ).read_text(encoding="utf-8")
    controller = (
        ALEXANDER / "justech_alexander_website" / "controllers" / "main.py"
    ).read_text(encoding="utf-8")
    assert "/doralex/logo/" in payload
    assert "/doralex/logo/<string:code>" in controller
    assert "dx_website_published" in controller
    assert "_CODE_RE" in controller
    assert "_fallback_svg" in controller
    assert "_reject_logo" in controller
    assert "website=False" in controller
    assert "base64.b64decode" in controller
    assert "res.partner" not in controller
    assert "ir.attachment" not in controller


def test_report_preview_covers_required_documents() -> None:
    preview = (
        ALEXANDER / "justech_alexander_reports" / "models" / "preview.py"
    ).read_text(encoding="utf-8")
    for key in (
        "quotation",
        "sale_order",
        "invoice",
        "credit_note",
        "purchase_order",
        "rfq",
        "delivery",
        "reception",
        "payment_receipt",
        "statement",
        "warranty",
    ):
        assert f'("{key}"' in preview
    assert "No consume NCF" in preview


def test_website_chrome_is_institutional() -> None:
    templates = (
        ALEXANDER / "justech_alexander_website" / "views" / "templates.xml"
    ).read_text(encoding="utf-8")
    assert "Contacto" in templates
    assert "Mi Empresa" in templates
    assert "My Company" in templates
    assert ">ERP<" in templates
    assert "+1 555" not in templates
    assert "yourcompany.example.com" not in templates


def test_report_extras_receive_company() -> None:
    inherits = (
        ALEXANDER / "justech_alexander_reports" / "reports" / "report_inherits.xml"
    ).read_text(encoding="utf-8")
    compose = (
        ALEXANDER / "justech_alexander_reports" / "models" / "report_compose.py"
    ).read_text(encoding="utf-8")
    layout = (
        ALEXANDER / "justech_alexander_reports" / "reports" / "layout.xml"
    ).read_text(encoding="utf-8")
    assert "_dx_sale_compose()" in inherits
    assert "_dx_invoice_compose()" in inherits
    assert "_dx_purchase_compose()" in inherits
    assert "_dx_picking_compose()" in inherits
    assert "self.company_id" in compose
    assert "o.company_id" in layout
    assert "doc.company_id" in layout


def test_no_vendor_edits_in_overlay() -> None:
    for path in _manifests():
        text = path.read_text(encoding="utf-8")
        assert "justech_alexander_" in path.parent.name
        assert "LGPL-3" in text


def test_ncf_guard_blocks_fiscal_post_without_real_range() -> None:
    manifest = (ALEXANDER / "justech_alexander_base" / "__manifest__.py").read_text(
        encoding="utf-8"
    )
    guard = (
        ALEXANDER / "justech_alexander_base" / "models" / "ncf_assignment.py"
    ).read_text(encoding="utf-8")
    assert "justech_l10n_do_ncf" in manifest
    assert "19.0.1.0.4" in manifest
    assert "justech.do.ncf.assignment.service" in guard
    assert "No crea rangos" in guard
    assert (
        "Debe configurar un rango NCF válido para esta compañía y tipo de "
        "comprobante antes de contabilizar."
    ) in guard
    assert "99000001" not in guard
    assert "consume_next" not in guard


def test_spanish_ui_overlay_does_not_edit_crm_core() -> None:
    overlay = (
        ALEXANDER / "justech_alexander_base" / "models" / "spanish_ui.py"
    ).read_text(encoding="utf-8")
    warranty_menu = (
        REPO_ROOT
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_warranty/views/menus.xml"
    ).read_text(encoding="utf-8")
    sale = (
        REPO_ROOT
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_approval_flow/models/sale_order.py"
    ).read_text(encoding="utf-8")
    assert "crm.crm_menu_leads" in overlay
    assert "Iniciativas" in overlay
    assert 'lang="es_DO"' in overlay or "lang='es_DO'" in overlay
    assert 'name="Tablero"' in warranty_menu
    assert "Estado de aprobación Justech" in sale


def test_ux_overlay_hides_technical_apps() -> None:
    ux = ALEXANDER / "justech_alexander_ux"
    manifest = (ux / "__manifest__.py").read_text(encoding="utf-8")
    menus = (ux / "views" / "menus.xml").read_text(encoding="utf-8")
    hooks = (ux / "hooks.py").read_text(encoding="utf-8")
    website = (ALEXANDER / "justech_alexander_website" / "__manifest__.py").read_text(
        encoding="utf-8"
    )
    fiscal = (
        REPO_ROOT
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_fiscal_admin/__manifest__.py"
    ).read_text(encoding="utf-8")
    assert '"application": False' in manifest
    assert "l10n_do_ecf_connector.ecf_documents_root" in menus
    assert "justech_l10n_do_base.menu_justech_do_fiscal_root" in menus
    assert "justech_l10n_do_reports.menu_justech_do_audit_root" in menus
    assert "menu_fiscal_reports_dgii" in menus
    assert "menu_fiscal_withholding" in menus
    assert "menu_fiscal_regularization" in menus
    assert "base.menu_administration" in menus
    assert "VISIBLE_APPS" in hooks
    assert "justech_alexander_admin" not in hooks.split("VISIBLE_APPS", 1)[1][:400]
    assert "apply_ecf_operational_state" in hooks
    assert "_hide_fiscal_leftovers" in hooks
    assert "justech_alexander.ecf_operational_enabled" in hooks
    settings = (ux / "models" / "res_config_settings.py").read_text(encoding="utf-8")
    assert "def get_values" in settings
    assert 'raw in ("True", "true", "1")' in settings
    assert '"application": False' in website
    assert '"application": False' in fiscal
    assert "UNINSTALL" not in hooks
