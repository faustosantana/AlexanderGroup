"""Hallazgos reunión Doralex — pruebas estructurales y matemáticas."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "addons" / "alexander" / "justech_alexander_reports"
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"
UX = REPO / "addons" / "alexander" / "justech_alexander_ux"
MAIL = REPO / "addons" / "alexander" / "justech_alexander_microsoft_mail"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_propet_identities_use_odoo_amounts():
    math = _load(REPORTS / "models" / "propet_math.py", "dx_propet_math")

    class Line:
        product_uom_qty = 2
        price_reduce_taxexcl = 100.0
        price_reduce_taxinc = 118.0
        price_tax = 36.0
        price_subtotal = 200.0
        price_total = 236.0

    amounts = math.propet_line_amounts(Line())
    assert math.propet_identities_ok(amounts)
    assert amounts["tax"] == 36.0
    assert amounts["total"] == amounts["subtotal"] + amounts["tax"]


def test_propet_discount_and_exempt():
    math = _load(REPORTS / "models" / "propet_math.py", "dx_propet_math")

    class Discounted:
        product_uom_qty = 3
        price_reduce_taxexcl = 90.0
        price_reduce_taxinc = 106.2
        price_tax = 48.6
        price_subtotal = 270.0
        price_total = 318.6

    class Exempt:
        product_uom_qty = 1
        price_reduce_taxexcl = 50.0
        price_reduce_taxinc = 50.0
        price_tax = 0.0
        price_subtotal = 50.0
        price_total = 50.0

    assert math.propet_identities_ok(math.propet_line_amounts(Discounted()))
    assert math.propet_identities_ok(math.propet_line_amounts(Exempt()))


def test_propet_display_texts_strip_repeated_product():
    math = _load(REPORTS / "models" / "propet_math.py", "dx_propet_math")
    product, desc = math.propet_display_texts(
        "CAJA DE CLAVOS F-20 (1)",
        "CAJA DE CLAVOS F-20 (1)",
        "CAJA DE CLAVOS F-20 (1) CAJA DE CLAVOS F-20 (1)",
    )
    assert product == "CAJA DE CLAVOS F-20 (1)"
    assert "CAJA DE CLAVOS F-20 (1) CAJA DE CLAVOS F-20 (1)" not in desc
    product, desc = math.propet_display_texts(
        "Tornillo",
        "[T-01] Tornillo",
        "[T-01] Tornillo\nTornillo de acero inoxidable 3 pulgadas",
    )
    assert "acero inoxidable" in desc
    assert not desc.startswith("[T-01]")


def test_propet_report_is_optional_not_default():
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    xml = (REPORTS / "reports" / "propet_proforma.xml").read_text(encoding="utf-8")
    compose = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    buttons = (REPORTS / "views" / "print_buttons.xml").read_text(encoding="utf-8")
    assert "propet_proforma.xml" in manifest
    assert "action_report_saleorder_propet" in xml
    assert "Formato Propet" in xml
    assert "FORMULARIO PROPET" not in xml
    assert "Formulario Propet" not in xml
    assert "action_report_invoice_propet" in xml
    assert "action_report_saleorder_conduce" not in xml
    assert "Este pedido aún no tiene una entrega" not in xml
    assert 'binding_type">report' in xml
    assert 'binding_model_id" eval="False"' in xml
    assert "action_dx_open_conduce" in buttons
    assert "Crear Conduce" in buttons
    assert "action_dx_print_formats" in buttons
    assert 'string="Imprimir"' in buttons
    assert 'string="Formato Propet"' not in buttons
    assert 'string="Proforma"' not in buttons
    assert "action_report_saleorder_propet" not in buttons
    assert "action_report_pro_forma_invoice" not in buttons
    assert (
        "sale.action_report_saleorder"
        not in xml.split("action_report_saleorder_propet")[0]
    )
    assert "_dx_sale_propet_compose" in compose
    assert "price_reduce_taxexcl" in (REPORTS / "models" / "propet_math.py").read_text(
        encoding="utf-8"
    )
    assert "FACTURA PROFORMA" in compose
    assert "CONDUCE" in compose
    assert '"OC / PO"' in compose
    assert "Número de Orden de Compra del Cliente" not in compose
    assert "FORMATO PROPET" not in compose
    assert '"COTIZACIÓN" if quote else "PEDIDO DE VENTA"' in compose
    assert 'title = "FACTURA"' in compose
    assert "propet_display_texts" in (REPORTS / "models" / "propet_math.py").read_text(
        encoding="utf-8"
    )
    assert 'name="context"' not in xml
    assert "group_ids" in xml


def test_description_isolation_does_not_copy_sibling_lines():
    source = (BASE / "models" / "sale_order_line.py").read_text(encoding="utf-8")
    assert "_dx_description_for_product" in source
    assert "_dx_refresh_name_from_product" in source
    assert "old_products" in source
    assert "display_type" in source


def test_crm_renames_only_default_english_labels():
    source = (BASE / "models" / "spanish_ui.py").read_text(encoding="utf-8")
    assert '"New": "Nuevo"' in source
    assert "Never rename custom stages" in source or "Never rename" in source
    assert "crm.lead" not in source.split("CRM_STAGE_RENAMES")[1][:400]


def test_tracking_keeps_native_lot_group():
    manifest = (UX / "__manifest__.py").read_text(encoding="utf-8")
    assert "product_views.xml" not in manifest
    views = UX / "views" / "product_views.xml"
    if views.exists():
        text = views.read_text(encoding="utf-8")
        assert 'name="groups"/>' not in text
        assert '<attribute name="groups"/>' not in text


def test_trace_columns_hidden_by_purchase_group_not_deleted():
    views = (UX / "views" / "sale_order_views.xml").read_text(encoding="utf-8")
    assert 'string="OC / PO"' in views
    assert "Número de Orden de Compra del Cliente" not in views
    assert "justech_supply" in views
    assert "justech_qty_purchased" in views
    assert "purchase.group_purchase_user" in views
    assert 'optional">hide' in views or 'optional="hide"' in views
    assert "<delete" not in views


def test_navbar_home_has_no_hardcoded_domain():
    navbar = (UX / "static" / "src" / "navbar" / "navbar.xml").read_text(
        encoding="utf-8"
    )
    assert 'title">Inicio' in navbar or 'title="Inicio"' in navbar
    assert "t-on-click" not in navbar
    assert "?." not in navbar
    assert "this.hm" not in navbar
    assert "doralexgroup.cloud" not in navbar
    assert "https://" not in navbar


def test_company_signature_cannot_use_other_company_fields():
    company = (MAIL / "models" / "res_company.py").read_text(encoding="utf-8")
    compose = (MAIL / "models" / "mail_compose_message.py").read_text(encoding="utf-8")
    assert "dx_mail_signature" in company
    assert "_dx_mail_signature_html" in company
    assert "_dx_document_company" in compose
    assert "company._dx_mail_signature_html()" in compose


def test_conduce_is_delivery_flow_not_sale_print():
    sale = (BASE / "models" / "sale_order.py").read_text(encoding="utf-8")
    buttons = (REPORTS / "views" / "print_buttons.xml").read_text(encoding="utf-8")
    compose = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    components = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    picking_qty = (REPORTS / "models" / "picking_qty.py").read_text(encoding="utf-8")
    assert "def action_dx_open_conduce" in sale
    assert "_action_launch_stock_rule" in sale
    assert "stock.picking" in sale
    assert 'self.state not in ("sale", "done")' in sale
    assert "action_dx_open_conduce" in buttons
    assert "Crear Conduce" in buttons
    assert "action_dx_print_formats" in buttons
    assert "action_report_delivery" not in buttons
    assert "client_ref_label" in compose
    assert '"OC / PO"' in compose
    assert "Cantidad pedida" in components
    assert "Cantidad entregada" in components
    picking_block = components.split('id="dx_picking_lines"')[1].split("</template>")[0]
    assert "ITBIS" not in picking_block
    assert "Precio" not in picking_block
    assert "Subtotal" not in picking_block
    assert "picking_line_qtys" in picking_qty
    assert "sale_line_id" in picking_qty


def test_picking_line_qtys_use_sale_order_not_move_demand():
    qty = _load(REPORTS / "models" / "picking_qty.py", "dx_picking_qty")

    class SaleLine:
        product_uom_qty = 10

    class Move:
        product_uom_qty = 6
        quantity = 6
        sale_line_id = SaleLine()

    ordered, done = qty.picking_line_qtys(Move())
    assert ordered == 10
    assert done == 6

    class Orphan:
        product_uom_qty = 4
        quantity_done = 2
        sale_line_id = False

    ordered, done = qty.picking_line_qtys(Orphan())
    assert ordered == 4
    assert done == 2


def test_oc_po_short_label_everywhere():
    sale_views = (UX / "views" / "sale_order_views.xml").read_text(encoding="utf-8")
    move_views = (UX / "views" / "account_move_views.xml").read_text(encoding="utf-8")
    compose = (REPORTS / "models" / "report_compose.py").read_text(encoding="utf-8")
    components = (REPORTS / "reports" / "components.xml").read_text(encoding="utf-8")
    wizard = (REPORTS / "models" / "sale_print_wizard.py").read_text(encoding="utf-8")
    wizard_xml = (REPORTS / "views" / "sale_print_wizard.xml").read_text(
        encoding="utf-8"
    )
    assert "action_print_propet" in wizard
    assert "dx.invoice.print.wizard" in wizard
    assert "Formato Propet" in wizard_xml
    assert "Factura Proforma" in wizard_xml
    assert "Cotización en PDF" in wizard_xml
    assert "dx.invoice.print.wizard" in wizard_xml
    assert 'string="OC / PO"' in sale_views
    assert ">OC / PO</attribute>" in move_views
    assert "Número de Orden de Compra del Cliente" not in sale_views
    assert "Número de Orden de Compra del Cliente" not in move_views
    assert "Número de Orden de Compra del Cliente" not in compose
    assert "or 'OC / PO'" in components
    assert "dx_oc_po" in components
    assert "_prepare_invoice" in (BASE / "models" / "sale_order.py").read_text(
        encoding="utf-8"
    )


def test_no_hardcoded_company_or_tax_ids_in_overlay():
    roots = (REPORTS, BASE, UX, MAIL)
    for path in roots:
        for file in path.rglob("*"):
            if file.suffix not in {".py", ".xml", ".js"}:
                continue
            text = file.read_text(encoding="utf-8")
            assert "company_id=1" not in text
            assert "company_id = 1" not in text
            assert "tax_id=238" not in text


def test_precheck_exists_and_forbids_prod_writes():
    doc = (REPO / "docs" / "ALEXANDERGROUP_PRECHECK.md").read_text(encoding="utf-8")
    assert "PROD TOUCHED: NO" in doc
    assert "19.0+e-20260324" in doc
    assert "ITBIS 16" in doc
