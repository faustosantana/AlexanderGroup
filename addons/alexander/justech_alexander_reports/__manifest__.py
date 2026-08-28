{
    "name": "Doralex Report Layout",
    "version": "19.0.2.0.0",
    "category": "Reporting",
    "summary": "Formatos A4 por empresa con identidad visual propia",
    "description": "Layout QWeb A4 por company_id del documento, con tema visual distinto para cada empresa Doralex. Hereda reportes oficiales de Odoo 19 sin rebindar acciones protegidas.",
    "author": "Justech",
    "website": "https://doralexgroup.cloud",
    "license": "LGPL-3",
    "depends": [
        "web",
        "sale",
        "purchase",
        "account",
        "stock",
        "l10n_do_accounting",
        "justech_warranty",
        "justech_alexander_base",
        "justech_alexander_admin",
    ],
    "data": [
        "security/ir.model.access.csv",
        "reports/paperformat.xml",
        "reports/layout.xml",
        "reports/brand_sync.xml",
        "reports/preview_templates.xml",
        "reports/report_inherits.xml",
        "reports/warranty_report.xml",
        "reports/statement.xml",
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
