# -*- coding: utf-8 -*-
{
    "name": "Justech Garantías",
    "summary": "Gestión profesional de garantías: registro por unidad (RC6.2), "
    "cobertura cliente vs. proveedor, reclamos (RMA) y configuración pre-venta.",
    "description": """
Justech Garantías
=================

Gestión integral del ciclo de vida de las garantías de los productos vendidos:
registro con vigencia calculada, duración por producto, generación automática
desde la factura de cliente, seguimiento **por unidad** (multi-serial) e
independiente del módulo de inventario, cobertura separada de cliente y
proveedor, reclamos parciales (RMA) y trazabilidad completa.

Forma parte de la base estándar de módulos Justgroup y sigue el estándar técnico
de estructura, seguridad, documentación, versionado y despliegue controlado.

RC6.2 (v19.0.1.9.0):
  * Nueva entidad `justech.warranty.unit`: una línea comercial (qty N) genera
    hasta N unidades de garantía trazables individualmente por serial de
    fabricante.
  * Configuración de garantía **antes de guardar** la cotización/factura
    (widget OWL trabaja con `NewId`).
  * Dependencia `stock` **removida**; `purchase` añadida para permitir enlazar
    orden de compra / factura de proveedor de forma opcional.
  * Cobertura cliente vs. proveedor con cálculo automático de gap.
  * Reclamos parciales por unidad.
""",
    "version": "19.0.1.9.1",
    "category": "Justech/Ventas",
    "author": "Justech",
    "maintainer": "Justech",
    "website": "https://justech.cloud",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "justech_core",
        "product",
        "sale",
        "account",
        "purchase",
        "justech_global_audit_log",
    ],
    "data": [
        "security/warranty_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/warranty_cron.xml",
        "data/warranty_config_data.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "wizard/warranty_line_config_wizard_views.xml",
        "views/warranty_views.xml",
        "views/warranty_claim_views.xml",
        "views/warranty_unit_views.xml",
        "views/warranty_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/warranty_dashboard_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_warranty/static/src/scss/warranty_lines.scss",
            "justech_warranty/static/src/js/warranty_config_button_field.js",
        ],
    },
    "demo": [],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "justech_register": {
        "module_code": "justech_warranty",
        "module_name": "Justech Garantías",
        "version": "19.0.1.9.1",
        "category": "sales",
        "country": "",
        "localization": "",
        "description": "Gestión de garantías por unidad, cobertura cliente/proveedor y reclamos (RMA).",
        "dependencies": [
            "justech_core",
            "product",
            "sale",
            "account",
            "purchase",
            "justech_global_audit_log",
        ],
        "always_enabled": False,
        "features": ["warranty", "rma", "multi_unit", "coverage_gap"],
    },
}
