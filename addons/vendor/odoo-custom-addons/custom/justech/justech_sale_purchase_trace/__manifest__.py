# -*- coding: utf-8 -*-
{
    "name": "Trazabilidad ventas/compras",
    "version": "19.0.1.2.10",
    "category": "Sales/Sales",
    "summary": "Generar OC y relacionar compra existente (OC o factura proveedor)",
    "description": """
Trazabilidad operativa Venta → Compra → Inventario — 19.0.1.2.10

- 1.2.10: Ocultar en header SO «Generar orden de compra» y «Relacionar compra existente»
  (entry único: Costos y Márgenes → Gestionar compras; métodos backend conservados)
- Generar orden de compra (reutiliza el motor de pendientes)
- Relacionar compra existente: Orden de compra o Factura de proveedor
- 1.2.6: cobertura de inventario usa reserva/hecho real, no demanda outgoing
- 1.2.6: no permite reducir qty vendida por debajo de qty comprada/vinculada
- 1.2.7: persistir sale_line_id al generar OC (OWL omitía campos readonly)
- 1.2.8: UX — ocultar Generar OC si pendiente=0; mensaje claro si cubierto
""",
    "author": "Justech",
    "website": "https://justech.do",
    "license": "LGPL-3",
    "depends": [
        "sale_management",
        "purchase",
        "sale_purchase",
        "sale_stock",
        "purchase_stock",
        "stock_account",
        "account",
        "bi_convert_purchase_from_sales",
    ],
    "data": [
        "security/trace_security.xml",
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/qty_assignment_views.xml",
        "wizards/buy_pending_wizard_views.xml",
        "wizards/link_existing_po_wizard_views.xml",
        "wizards/diagnostic_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_sale_purchase_trace/static/src/js/form_link_po_skip_save.js",
            "justech_sale_purchase_trace/static/src/scss/purchase_wizards.scss",
        ],
    },
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
