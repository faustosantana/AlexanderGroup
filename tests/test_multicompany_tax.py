"""Estructura del fix multiempresa de account.tax (Alexander / Odoo 19)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"

REQUIRED_TESTS = (
    "test_shared_product_tax_mayuma",
    "test_shared_product_tax_rempart",
    "test_shared_product_tax_doralex",
    "test_shared_product_tax_pinaria",
    "test_shared_product_tax_dominion",
    "test_shared_product_tax_blue_elite",
    "test_multicompany_user_tax_access",
    "test_sales_tax_company_matches_order",
    "test_purchase_tax_company_matches_po",
    "test_invoice_tax_company_matches_move",
)


def test_manifest_version_and_files() -> None:
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.1.0.21" in manifest
    assert "purchase" in manifest
    for rel in (
        "models/account_tax.py",
        "models/product_template.py",
        "models/sale_order_line.py",
        "models/purchase_order_line.py",
        "models/account_move_line.py",
        "models/account_fiscal_position.py",
        "models/multicompany_tax_service.py",
        "tests/test_multicompany_tax.py",
    ):
        assert (BASE / rel).is_file(), rel


def test_named_odoo_tests_exist() -> None:
    src = (BASE / "tests" / "test_multicompany_tax.py").read_text(encoding="utf-8")
    for name in REQUIRED_TESTS:
        assert f"def {name}(" in src, name


def test_native_company_filter_not_global_tax() -> None:
    tax = (BASE / "models" / "account_tax.py").read_text(encoding="utf-8")
    product = (BASE / "models" / "product_template.py").read_text(encoding="utf-8")
    assert "_filter_taxes_by_company" in tax
    assert "_dx_accessible_taxes" in tax
    assert "company_id = False" not in tax
    assert "domain_force" not in tax
    assert "perm_read" not in tax
    assert "_dx_taxes_for_company" in product
    assert "_dx_mirror_shared_product_taxes" in product
    assert "company_id = False" in product or "not rec.company_id" in product


def test_no_record_rule_weakening() -> None:
    for path in BASE.rglob("*"):
        if path.suffix not in {".py", ".xml", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.name == "account_tax.py":
            assert "domain_force" not in text
            continue
        assert "account.tax.rule" not in text
        if path.suffix == ".xml":
            assert "model_account_tax" not in text or "ir.rule" not in text


def test_no_accounting_admin_grant() -> None:
    for path in BASE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "group_account_manager" not in text or path.name == "res_company.py"
    groups = (BASE / "models" / "res_groups.py").read_text(encoding="utf-8")
    assert "group_account_manager" not in groups


def test_document_guards_use_record_company() -> None:
    sale = (BASE / "models" / "sale_order_line.py").read_text(encoding="utf-8")
    purchase = (BASE / "models" / "purchase_order_line.py").read_text(encoding="utf-8")
    move = (BASE / "models" / "account_move_line.py").read_text(encoding="utf-8")
    assert "order_id.company_id" in sale
    assert "_dx_check_sale_tax_company" in sale
    assert "order_id.company_id" in purchase
    assert 'move_id.state == "posted"' in move or "move_id.state == 'posted'" in move
    assert "El impuesto seleccionado pertenece a otra empresa" in (
        BASE / "models" / "account_tax.py"
    ).read_text(encoding="utf-8")


def test_diagnostic_command_exists() -> None:
    service = (BASE / "models" / "multicompany_tax_service.py").read_text(
        encoding="utf-8"
    )
    tool = REPO / "tools" / "check_multicompany_tax_integrity.py"
    assert "def check_multicompany_tax_integrity" in service
    assert "def fix_draft_cross_company_taxes" in service
    assert "POSTED_CROSS_COMPANY_TAX" in service
    assert tool.is_file()
    assert "check_multicompany_tax_integrity" in tool.read_text(encoding="utf-8")


def test_catalog_operational_companies() -> None:
    catalog = (BASE / "models" / "catalog.py").read_text(encoding="utf-8")
    assert "def operational_companies" in catalog
    assert "profile_for_company" in catalog


def test_product_tax_write_does_not_reenter_guard() -> None:
    product = (BASE / "models" / "product_template.py").read_text(encoding="utf-8")
    assert "dx_skip_tax_company_guard" in product
    assert "_dx_set_product_taxes" in product
    assert "default_get" in product
    assert "account_sale_tax_id.ids" in product
    assert "account_purchase_tax_id.ids" in product
    assert "not in operational" in product
    assert "_force_default_tax" in product
    assert "_dx_visible_product_taxes" in product
    assert "_dx_mask_tax_rows" in product
    assert "_web_read_visible_taxes" in product
    assert "if key not in _TAX_M2M" in product
    assert "tax.company_id.id in allowed_ids" in product
    assert "web_read.__get__" not in product


def test_itbis_display_names_are_per_company() -> None:
    from tools.alexander_tax_labels.labels import EXPECTED_ITBIS_LABELS

    assert EXPECTED_ITBIS_LABELS["DOR"]["sale"] == "ITBIS venta Doralex"
    assert EXPECTED_ITBIS_LABELS["DOR"]["purchase"] == "ITBIS compra Doralex"
    assert EXPECTED_ITBIS_LABELS["MAY"]["sale"] == "ITBIS venta El Mayuma"
    assert EXPECTED_ITBIS_LABELS["REM"]["purchase"] == "ITBIS compra Rempart"
    catalog = (BASE / "models" / "catalog.py").read_text(encoding="utf-8")
    assert "def itbis_display_name" in catalog


def test_init_imports_tax_models() -> None:
    init = (BASE / "models" / "__init__.py").read_text(encoding="utf-8")
    for name in (
        "account_tax",
        "product_template",
        "purchase_order_line",
        "account_move_line",
        "account_fiscal_position",
        "multicompany_tax_service",
    ):
        assert name in init


def test_hooks_run_tax_cleanup() -> None:
    hooks = (BASE / "hooks.py").read_text(encoding="utf-8")
    assert "justech.alexander.multicompany.tax.service" in hooks
    assert "_dx_apply_safe_product_tax_cleanup" in hooks
