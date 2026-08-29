{
    "name": "Doralex Report Layout",
    "version": "19.0.3.8.3",
    "category": "Reporting",
    "summary": "V5.3: pulido de cotización y suite documental por identidad",
    "description": "Microajustes V5.3 sobre base V5.2. Misma identidad en factura, NC, OC, recibo, estado y picking. No cambia fiscalidad.",
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
        "reports/headers.xml",
        "reports/layout.xml",
        "reports/components.xml",
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
