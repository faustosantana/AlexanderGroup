"""Pruebas estructurales del rediseño de reportes Doralex."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "addons" / "alexander" / "justech_alexander_reports"
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_six_company_themes_in_css():
    css = (REPORTS / "static" / "src" / "css" / "report.css").read_text(
        encoding="utf-8"
    )
    for code in ("DOR", "PIN", "DOM", "MAY", "REM", "BLU"):
        assert f"dx-theme-{code}" in css
    assert "DejaVu Sans" in css
    assert "page-break-inside: avoid" in css
    assert "#E86A12" in css
    assert "#C41E3A" in css
    assert "#2AA8A4" in css
    assert "#2EC4B6" in css
    assert "#3D7AB5" in css
    assert "#0A3D91" in css


def test_layout_uses_document_company():
    layout = (REPORTS / "reports" / "layout.xml").read_text(encoding="utf-8")
    assert "o.company_id" in layout
    assert "web.external_layout" in layout
    assert "dx-theme-" in layout
    assert "external_layout_force_document_company" in layout
    assert "address_layout" not in layout


def test_official_report_names_not_rebound():
    inherits = (REPORTS / "reports" / "report_inherits.xml").read_text(encoding="utf-8")
    assert "sale.report_saleorder_document" in inherits
    assert "account.report_invoice_document" in inherits
    assert "purchase.report_purchaseorder_document" in inherits
    assert 'inherit_id="sale.report_saleorder"' not in inherits
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "l10n_do_accounting" in manifest


def test_render_forces_company_context():
    py = (REPORTS / "models" / "ir_actions_report.py").read_text(encoding="utf-8")
    assert "with_company" in py
    assert "_dx_company_from_records" in py


def test_catalog_brand_colors_match_logos():
    catalog = (BASE / "models" / "catalog.py").read_text(encoding="utf-8")
    assert '"color": "#E86A12"' in catalog
    assert '"color": "#C41E3A"' in catalog
    assert '"color": "#2AA8A4"' in catalog
    assert '"color": "#2EC4B6"' in catalog
    assert '"color": "#1A1A1A"' in catalog
    assert '"color": "#0A3D91"' in catalog
