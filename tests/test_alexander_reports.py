"""Pruebas estructurales V5.3: pulido + suite documental por identidad."""

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
    assert "dx-h-dor-rail" in css
    assert "dx-h-dor-col" in css
    assert "dx-h-dor-vendor" in css
    assert "dx-ncf-hero" in css
    assert "dx-ncf-pending" in css
    assert "padding-top: 0 !important" in css
    assert "dx-h-pin-c" in css
    assert "dx-h-dom-rail" in css
    assert "dx-h-may-title" in css
    assert "dx-h-rem-rule" in css
    assert "dx-h-rem-logo" in css
    assert "dx-h-blu-logo" in css
    for layout in ("dor", "pin", "dom", "may", "rem", "blu"):
        assert f"dx-table-{layout}" in css
        assert f"dx-totals-{layout}" in css
    assert "dx-sign-wrap" in css
    assert "dx-sign-pin" in css
    assert "dx-dom-totals-shift" in css
    assert "dx-pin-end" in css
    assert "dx-rem-totals-box" in css
    assert "dx-blu-totals-box" in css
    assert "dx-may-terms-wide" in css
    assert "background: #ffffff !important" in css
    assert "#f7f7f7" not in css
    assert "position:absolute" not in css
    assert "position: absolute" not in css
    assert "#E46018" in css
    assert "#30A83C" in css
    assert "#50B0B0" in css
    assert "#F09040" in css
    assert "#54B4A8" in css
    assert "#3048A8" in css
    assert "#0B1F3A" in css
    assert "#18B4F0" in css


def test_six_real_headers_and_sale_compositions():
    headers = (REPORTS / "reports" / "headers.xml").read_text(encoding="utf-8")
    for name in (
        "dx_header_doralex",
        "dx_header_pinaria",
        "dx_header_dominion",
        "dx_header_mayuma",
        "dx_header_rempart",
        "dx_header_blueelite",
        "dx_footer_doralex",
        "dx_footer_pinaria",
        "dx_footer_dominion",
        "dx_footer_mayuma",
        "dx_footer_rempart",
        "dx_footer_blueelite",
    ):
        assert name in headers
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    for name in (
        "dx_sale_doralex",
        "dx_sale_pinaria",
        "dx_sale_dominion",
        "dx_sale_mayuma",
        "dx_sale_rempart",
        "dx_sale_blueelite",
        "dx_sale_composition",
    ):
        assert name in comps
    assert "chunk['src']" in comps
    assert "dx-may-meta" in comps
    assert "dx-table-{{ dx.get('layout')" in comps
    assert "dx-totals-{{ dx.get('layout')" in comps
    assert "dx-pin-terms-full" in comps
    assert "dx-sign-wrap" in comps
    assert "dx-total-row" in comps
    assert "dx-dor-end" in comps
    assert "dx-dom-totals-shift" in comps
    assert "dx-may-terms-wide" in comps
    assert "dx-rem-totals-box" in comps
    assert "dx-blu-totals-box" in comps
    assert "dx-blu-asym" in comps
    assert "dx-pin-titlecell" in comps
    assert "dx-dor-client" in comps
    assert "dx-h-dor-vendor" in headers
    assert "dx_document_end" in comps
    assert "dx-ncf-hero" in comps
    assert "Pendiente de NCF" in comps
    assert "dx-sign-table" not in comps
    assert "dx-zone-bottom" not in comps
    assert "PAGO NO APLICADO / ANTICIPO" in comps
    assert "Esperada" in comps
    assert "dx-h-rem-id" in headers
    assert "dx-rem-mast" not in comps
    assert 'border="0"' in headers
    assert 'border="0"' in comps


def test_layout_uses_document_company():
    layout = (REPORTS / "reports" / "layout.xml").read_text(encoding="utf-8")
    assert "o.company_id" in layout
    assert "web.external_layout" in layout
    assert "dx_header_doralex" in layout
    assert "dx_header_pinaria" in layout
    assert "dx_header_dominion" in layout
    assert "dx_header_mayuma" in layout
    assert "dx_header_rempart" in layout
    assert "dx_header_blueelite" in layout
    assert "_dx_header_meta_for" in layout
    assert "dx_report_footer_text" not in layout
    extras = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    assert "dx_sale_composition" in extras
    assert "dx_invoice_composition" in extras
    assert "dx_payment_composition" in extras
    assert "spacer_chunks" in extras
    assert "dx-amount-hero" in extras
    assert "<br" not in extras or extras.count("<br") == 0


def test_invoice_edi_template_attaches_pdf():
    xml = (REPORTS / "data" / "mail_templates.xml").read_text(encoding="utf-8")
    assert "account.email_template_edi_invoice" in xml
    assert "account.account_invoices" in xml
    assert "_dx_attach_invoice_edi_pdf" in xml
    py = (REPORTS / "models" / "ir_actions_report.py").read_text(encoding="utf-8")
    assert "def _dx_attach_invoice_edi_pdf" in py
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "data/mail_templates.xml" in manifest


def test_official_report_names_not_rebound():
    inherits = (REPORTS / "reports" / "report_inherits.xml").read_text(encoding="utf-8")
    assert "sale.report_saleorder_document" in inherits
    assert "account.report_invoice_document" in inherits
    assert 'inherit_id="sale.report_saleorder"' not in inherits
    assert "_dx_sale_compose" in inherits
    assert "dx-composition-wrap" in inherits
    assert 'position="replace"' not in inherits
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "l10n_do_accounting" in manifest
    assert "headers.xml" in manifest
    assert "components.xml" in manifest


def test_render_forces_company_context():
    py = (REPORTS / "models" / "ir_actions_report.py").read_text(encoding="utf-8")
    assert "with_company" in py
    assert "_dx_lang_from_records" in py


def test_statement_uses_python_rows():
    xml = (REPORTS / "reports" / "statement.xml").read_text(encoding="utf-8")
    assert "bundle['rows']" in xml
    assert "ESTADO DE CUENTA" in xml
    assert "dx-stmt-top" in xml
    assert "dx-meta-grid" not in xml
    assert "bundle.get('layout')" in xml
    py = (REPORTS / "models" / "res_partner.py").read_text(encoding="utf-8")
    assert "_dx_statement_bundles" in py
    assert "Saldo a favor" in py


def test_payment_receipt_has_hero_and_anticipo():
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    assert "dx-amount-hero" in comps
    assert "PAGO NO APLICADO" in comps
    catalog = (BASE / "models" / "catalog.py").read_text(encoding="utf-8")
    assert '"color": "#E86A12"' in catalog
    assert '"color": "#0A3D91"' in catalog


def test_paperformat_is_compact():
    xml = (REPORTS / "reports" / "paperformat.xml").read_text(encoding="utf-8")
    assert ">52</field>" in xml
    assert ">48</field>" in xml
    assert ">16</field>" in xml
    assert ">42</field>" not in xml
    assert "paperformat_doralex_a5" in xml
    assert ">44</field>" in xml
    assert ">40</field>" in xml
    assert "action_report_payment_receipt" in xml


def test_invoice_title_is_factura_not_borrador():
    py = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    assert '"FACTURA"' in py
    assert '"NOTA DE CRÉDITO"' in py
    assert '"COTIZACIÓN"' in py
    assert '"Pendiente"' in py
    assert "Pendiente de NCF" not in py
    assert "ncf_pending" in py
    assert "_dx_layout" in py
    assert "justech_do_ncf" in py
    assert "background:#ffffff" in py
    assert "#f7f7f7" not in py
    assert '"layout"' in py
    company = (REPORTS / "models" / "res_company.py").read_text(encoding="utf-8")
    assert '"logo_h": 38' in company
    assert '"logo_h": 44' in company
    assert '"logo_w": 68' in company
    assert '"layout": "pin"' in company
    assert "def _dx_header_meta_for" in company
    assert "def _dx_report_logo_src" in company
    assert "def _dx_logo_content_bbox" in company
    assert "Aceptado por el cliente" in py
    assert "_dx_purchase_compose" in py
    assert "_dx_picking_compose" in py
    assert "_dx_payment_compose" in py
    warranty = (REPORTS / "reports" / "warranty_report.xml").read_text(encoding="utf-8")
    assert "CERTIFICADO DE GARANTÍA" in warranty
    assert "Certificado de Garantía" in warranty
    assert '"show_signature": False' in py
    assert '"Solicitado por"' in py
    assert '"Entregado por proveedor"' in py
    assert '"Recibido por"' in py


def test_layout_forces_document_company_and_continue_header():
    layout = (REPORTS / "reports" / "layout.xml").read_text(encoding="utf-8")
    assert "o.company_id.sudo()" in layout
    assert "dx-h-continue" in layout
    assert "dx-h-full" in layout
    assert "dxApplyContinueHeader" in layout
    assert 'bits[0] === "page"' in layout
    css = (REPORTS / "static" / "src" / "css" / "report.css").read_text(
        encoding="utf-8"
    )
    assert ".dx-h-continue" in css


def test_picking_uses_external_layout_and_unique_address():
    inherits = (REPORTS / "reports" / "report_inherits.xml").read_text(encoding="utf-8")
    assert "stock.report_picking" in inherits
    comps = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    pick = comps.split('id="dx_picking_composition"')[1].split("</template>")[0]
    assert "embed_masthead" in pick
    assert "dx-pick-ident-title" in pick
    assert pick.count("dx['partner']['street']") == 0
    paper = (REPORTS / "reports" / "paperformat.xml").read_text(encoding="utf-8")
    assert "stock.action_report_picking" in paper
    assert "stock.action_report_delivery" in paper
    py = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    assert '"embed_masthead": incoming' in py


def test_statement_credit_balance_not_negative_total():
    py = (REPORTS / "models" / "res_partner.py").read_text(encoding="utf-8")
    assert "a favor" in py
    assert "Saldo a favor" in py
    assert "abs(running)" in py


def test_mail_from_skips_aliases_and_uses_company():
    mail = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_microsoft_mail"
        / "models"
        / "mail_mail.py"
    ).read_text(encoding="utf-8")
    assert "_dx_related_company" in mail
    assert "company._dx_outgoing_address()" in mail
    compose = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_microsoft_mail"
        / "models"
        / "mail_compose_message.py"
    ).read_text(encoding="utf-8")
    assert "_dx_outgoing_address" in compose


def test_mail_from_is_administracion_not_alias():
    mail = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_microsoft_mail"
        / "models"
        / "res_company.py"
    ).read_text(encoding="utf-8")
    assert "def _dx_outgoing_address" in mail
    assert "administracion@%s" in mail
    assert "_OUTGOING_SKIP_LOCALS" in mail
    assert '"ventas"' in mail
    assert '"facturacion"' in mail
    client = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_microsoft_mail"
        / "models"
        / "graph_client.py"
    ).read_text(encoding="utf-8")
    assert "sentitems" in client
    assert "sendMail" in client
