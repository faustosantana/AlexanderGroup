"""Pruebas estructurales del rediseño visual V2 de reportes Doralex."""

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
    assert "#E46018" in css
    assert "#30A83C" in css
    assert "#C00000" in css
    assert "#54B4A8" in css
    assert "#FC9048" in css
    assert "#3048A8" in css
    assert "#243C9C" in css
    assert "#18B4F0" in css
    assert "dx-composition" in css
    assert "dx-page-stack" in css
    assert "min-height: 200mm" in css
    assert "white-space: nowrap" in css
    assert "position:absolute" not in css
    assert "position: absolute" not in css


def test_layout_uses_document_company():
    layout = (REPORTS / "reports" / "layout.xml").read_text(encoding="utf-8")
    assert "o.company_id" in layout
    assert "web.external_layout" in layout
    assert "dx-theme-" in layout
    assert "external_layout_force_document_company" in layout
    assert "_dx_header_identity_for" in layout
    assert "dx-head-doc" in layout
    assert "dx-pin-titleband" in layout
    assert "dx-dom-titlebox" in layout
    assert "dx-may-accent" in layout
    assert "dx-rem-logo" in layout
    assert "dx-blu-slab" in layout
    assert "RNC" in layout
    assert "dx_report_footer_text" not in layout
    extras = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    assert "dx_extras_mode" in extras
    assert "dx_sale_composition" in extras
    assert "dx_invoice_composition" in extras
    assert "dx_payment_composition" in extras
    assert "dx_purchase_composition" in extras
    assert "dx_picking_composition" in extras
    assert "dx-page-stack" in extras
    assert "dx-amount-hero" in extras
    assert "Importe acreditado" in extras
    assert "<br" not in extras or extras.count("<br") == 0


def test_official_report_names_not_rebound():
    inherits = (REPORTS / "reports" / "report_inherits.xml").read_text(encoding="utf-8")
    assert "sale.report_saleorder_document" in inherits
    assert "account.report_invoice_document" in inherits
    assert "purchase.report_purchaseorder_document" in inherits
    assert 'inherit_id="sale.report_saleorder"' not in inherits
    assert "_dx_sale_compose" in inherits
    assert "_dx_invoice_compose" in inherits
    assert "_dx_payment_compose" in inherits
    assert "_dx_purchase_compose" in inherits
    assert "_dx_picking_compose" in inherits
    assert "dx-composition-wrap" in inherits
    assert 'position="replace"' not in inherits
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "l10n_do_accounting" in manifest
    assert "components.xml" in manifest


def test_render_forces_company_context():
    py = (REPORTS / "models" / "ir_actions_report.py").read_text(encoding="utf-8")
    assert "with_company" in py
    assert "_dx_lang_from_records" in py


def test_statement_uses_python_rows():
    xml = (REPORTS / "reports" / "statement.xml").read_text(encoding="utf-8")
    assert "bundle['rows']" in xml
    assert "bundle['anchor']" in xml
    assert "ESTADO DE CUENTA" in xml
    assert "dx-kpi" in xml
    py = (REPORTS / "models" / "res_partner.py").read_text(encoding="utf-8")
    assert "_dx_statement_bundles" in py
    assert "invoice_date or move.date" in py
    assert "_dx_line_residual_at_cutoff" in py
    assert "assert_receivable_invariants" in py
    assert "Saldo a favor" in py
    assert "Créditos / anticipos" in py
    assert "moves[0]" in py
    assert "dx_statement_cutoff" in py
    assert "asset_receivable" in py


def test_payment_receipt_has_hero_and_anticipo():
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    assert "dx-amount-hero" in comps
    assert "PAGO NO APLICADO" in comps
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    assert "dx_purchase_composition" in comps
    catalog = (BASE / "models" / "catalog.py").read_text(encoding="utf-8")
    assert '"color": "#E86A12"' in catalog
    assert '"color": "#C41E3A"' in catalog
    assert '"color": "#2AA8A4"' in catalog
    assert '"color": "#2EC4B6"' in catalog
    assert '"color": "#1A1A1A"' in catalog
    assert '"color": "#0A3D91"' in catalog


def test_paperformat_is_compact():
    xml = (REPORTS / "reports" / "paperformat.xml").read_text(encoding="utf-8")
    assert ">36</field>" in xml
    assert ">32</field>" in xml
    assert ">16</field>" in xml
    assert ">46</field>" not in xml
    assert "paperformat_doralex_a5" in xml
    assert ">A5</field>" in xml
    assert "action_report_payment_receipt" in xml


def test_invoice_title_is_factura_not_borrador():
    py = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    assert '"FACTURA"' in py
    assert '"NOTA DE CRÉDITO"' in py
    assert '"COTIZACIÓN"' in py
    assert '"RECIBO DE PAGO"' in py
    assert '"BORRADOR"' in py
    assert '"Pendiente"' in py
    assert "Sin numerar" not in py
    assert "justech_do_ncf" in py
    assert "def _dx_terms" in py
    assert "def _dx_salesperson" in py
    assert "Pago manual" in py
    company = (REPORTS / "models" / "res_company.py").read_text(encoding="utf-8")
    assert '"logo_h": 28' in company
    assert '"layout": "pin"' in company
    assert "def _dx_report_theme" in company
    assert "def _dx_header_identity_for" in company
    assert "def _dx_legal_display" in company
    assert "Aceptado por el cliente" in py
    assert "Solicitado por" in py
    assert "Entregado por proveedor" in py
    assert "Preparado por" in py
    assert "Recibido conforme" in py
    assert "_dx_purchase_compose" in py
    assert "_dx_picking_compose" in py
