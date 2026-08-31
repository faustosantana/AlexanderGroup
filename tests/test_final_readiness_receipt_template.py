"""Structure checks for the multi-invoice receipt template (no Odoo runtime)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XML = (
    ROOT
    / "addons/vendor/odoo-custom-addons/third_party/multi_invoice_manual_payment_prod/views/report_payment_receipt.xml"
)
PY = (
    ROOT
    / "addons/vendor/odoo-custom-addons/third_party/multi_invoice_manual_payment_prod/models/account_payment.py"
)
MANIFEST = (
    ROOT
    / "addons/vendor/odoo-custom-addons/third_party/multi_invoice_manual_payment_prod/__manifest__.py"
)


def test_receipt_template_has_alexander_columns():
    xml = XML.read_text()
    for needle in (
        "FACTURA",
        "NCF",
        "FECHA FACTURA",
        "FECHA VENCIMIENTO",
        "MONTO ORIGINAL",
        "SALDO ANTES",
        "MONTO APLICADO",
        "SALDO RESULTANTE",
        "TOTAL RECIBIDO",
        "TOTAL APLICADO",
        "SALDO NO APLICADO",
        "FACTURA PROVEEDOR",
        "justech_applied_invoice_ids",
    ):
        assert needle in xml, needle
    assert "justech_alexander_reports" not in xml
    assert 'inherit_id="account.report_payment_receipt_document"' in xml


def test_receipt_payload_helper_exists():
    src = PY.read_text()
    assert "def _justech_receipt_payload" in src
    assert "balance_before" in src
    assert "unapplied" in src


def test_module_version_bumped_without_new_alexander_qweb():
    text = MANIFEST.read_text()
    assert "19.0.1.5.5" in text
    assert "justech_alexander_reports" not in text


def test_cost_link_wizard_reloads_lines_on_po_write():
    root = Path(__file__).resolve().parents[1]
    py = (
        root
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_purchase_sale_margin_control/wizard/cost_ops_wizards.py"
    ).read_text()
    xml = (
        root
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_purchase_sale_margin_control/wizard/cost_ops_wizard_views.xml"
    ).read_text()
    manifest = (
        root
        / "addons/vendor/odoo-custom-addons/custom/justech/justech_purchase_sale_margin_control/__manifest__.py"
    ).read_text()
    assert "def _reload_document_lines" in py
    assert "justech_skip_link_reload" in py
    assert 'string="Cargar artículos"' in xml
    assert 'invisible="not purchase_order_id"' not in xml
    assert "19.0.8.29.39" in manifest
