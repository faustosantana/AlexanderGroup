{
    "name": "Doralex Report Layout",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Layout A4 central y vista previa de documentos Doralex",
    "description": "Un solo layout QWeb/CSS por company_id para cotización, pedido, factura, nota de crédito, compra, RFQ, conduce, recepción, recibo, estado de cuenta y garantía. Sin Studio.",
    "author": "Justech",
    "website": "https://doralexgroup.cloud",
    "license": "LGPL-3",
    "depends": [
        "web",
        "sale",
        "purchase",
        "account",
        "stock",
        "justech_warranty",
        "justech_alexander_base",
        "justech_alexander_admin",
    ],
    "data": [
        "security/ir.model.access.csv",
        "reports/paperformat.xml",
        "reports/layout.xml",
        "reports/preview_templates.xml",
        "reports/report_inherits.xml",
        "reports/warranty_report.xml",
        "views/preview_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "justech_alexander_reports/static/src/css/report.css"
        ]
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
