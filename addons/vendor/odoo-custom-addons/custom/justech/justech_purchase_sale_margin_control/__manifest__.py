# -*- coding: utf-8 -*-
{
    "name": "Costos y Márgenes",
    "version": "19.0.8.29.38",
    "category": "Sales/Sales",
    "summary": "App independiente + trazabilidad cruzada Ventas/Compras/Facturas",
    "description": """
Justech Purchase Sale Margin Control 19.0.8.29.37
================================================

- 8.29.37: Integridad cobertura — upsert idempotente (no 3+3=6); refresh post-apply;
  cancel/unlink libera cobertura; gate docs cancelados solo si activos; precio 0 bloqueado;
  UX PO vincular/desvincular; vendedor = usuario actual al crear SO
- 8.29.36: ACL Vincular a venta sin Sales ACL; display_cost sin doble estimado+real
- 8.29.35: Estabilización reportes — Usuario/Responsable implican caps sección; sync menús; tests regresión
- 8.29.34: Restaurar app Costos y Márgenes; PO/MTX UX limpia; estados costos comerciales
- 8.29.33: Hotfix Línea venta PO→SO (domain sin filtro producto); tabla SO limpia; hub sin form técnico
- 8.29.32: Hotfix Vincular a venta — ACL seguro MTX elevate; header PO limpio; estados verde/naranja/rojo
- 8.29.31: PO Vincular a venta (wizard simple); ACL-safe facturas; hub Detalle solo parcial/pendiente
- 8.29.30: Cobertura costo = inventario + OC abierta; no excluir inventario en refresh; hub UX Inventario/En compra/Sin cubrir
- 8.29.29: UX SO simplificada; Costos y Márgenes vista negocio; confirmar enlaces inequívocos; ocultar botones técnicos
- 8.29.28: Bloqueo factura RD$0 sin recepción; costo mixto real+estimado; docs clickables
- 8.29.27: Auto-confirm costos al 100%; ocultar Calcular/Ver operación; OC canceladas fuera de UX; bill 0 no pisa estimado
- 8.29.26: Hub inline sale-first (Gestionar costo por línea; wizard 4 pasos solo masivo)
""",
    "author": "Justech",
    "website": "https://justech.do",
    "license": "LGPL-3",
    "depends": [
        "sale_management",
        "purchase",
        "account",
        "stock",
        "sale_purchase",
        "purchase_stock",
        "sale_stock",
        "mail",
    ],
    "data": [
        "security/margin_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
        "views/cost_link_views.xml",
        "views/cost_allocation_views.xml",
        "views/margin_snapshot_views.xml",
        "views/reconciliation_rule_views.xml",
        "views/margin_transaction_views.xml",
        "views/margin_board_views.xml",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
        "views/payable_auxiliary_views.xml",
        "views/account_move_views.xml",
        "wizard/allocate_wizard_views.xml",
        "wizard/prorate_wizard_views.xml",
        "wizard/backfill_wizard_views.xml",
        "wizard/add_purchase_wizard_views.xml",
        "wizard/relate_sale_wizard_views.xml",
        "wizard/ux_action_wizard_views.xml",
        "wizard/uat_fixture_wizard_views.xml",
        "wizard/manage_purchases_wizard_views.xml",
        "wizard/cost_ops_wizard_views.xml",
        "wizard/product_cost_wizard_views.xml",
        "wizard/historical_cost_wizard_views.xml",
        "wizard/cost_breakdown_wizard_views.xml",
        "wizard/link_sale_wizard_views.xml",
        "views/register_cost_wizard_views.xml",
        "views/register_sale_wizard_views.xml",
        "views/create_transaction_wizard_views.xml",
        "report/cost_vs_sale_report.xml",
        "report/payable_auxiliary_report.xml",
        "report/margin_historical_report.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_purchase_sale_margin_control/static/src/css/margin_board.css",
            "justech_purchase_sale_margin_control/static/src/css/cost_vs_sale_wizard.css",
            "justech_purchase_sale_margin_control/static/src/js/cost_vs_sale_wizard.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
