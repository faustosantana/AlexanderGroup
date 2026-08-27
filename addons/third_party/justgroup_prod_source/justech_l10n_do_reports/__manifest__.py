{
    "name": "Justech Dominican Fiscal Reports",
    "version": "19.0.1.24.8",
    "category": "Accounting/Localizations/Reporting",
    "summary": "DGII reports 606–609, 623 — exportadores oficiales",
    "description": """
Dominican DGII fiscal reports for Justech.

- Format 606 (purchases) — exportador Excel DGII
- Format 607 (sales) — exportador Excel DGII
- Format 608 (voided NCF)
- Validation wizard and export history
    """,
    "author": "Justech",
    "website": "https://www.justgroup.app",
    "depends": [
        "accountant",
        "justech_l10n_do_ncf",
        "justech_fiscal_admin",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/justech_l10n_do_reports_rules.xml",
        "views/fiscal_report_views.xml",
        "views/dgii_report_review_views.xml",
        "views/dgii_report_pending_tray_views.xml",
        "views/fiscal_report_actions.xml",
        "wizard/fiscal_report_wizard_views.xml",
        "wizard/dgii_export_blocker_wizard_views.xml",
        "views/menu.xml",
        "views/dgii_tax_classification_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_l10n_do_reports",
        "module_name": "Justech Dominican Fiscal Reports",
        "version": "19.0.1.24.8",
        "category": "reports",
        "country": "DO",
        "localization": "l10n_do",
        "description": "DGII reports 606, 607, 608, 623",
        "dependencies": ["justech_l10n_do_ncf"],
        "always_enabled": True,
        "required_module": True,
        "features": [
            {"code": "l10n_do_reports", "name": "DO DGII Reports"},
        ],
    },
    "justech_admin_center": {
        "product_code": "fiscal",
        "functional_name": "Reportes DGII",
        "short_description": "606, 607, 608, 609, 623 y flujo de declaración",
        "long_description": "Qué es: generador de reportes DGII. Para qué sirve: preparar y declarar 606/607 y relacionados. Procesos: cierre fiscal mensual. Datos: facturas, NCF, retenciones. Crítico: sí. Ámbito: por empresa. Al desactivar: conserva reportes históricos; bloquea nuevas generaciones. Capacidad transversal con retenciones.",
        "what_it_does": "Genera y gestiona reportes de cumplimiento DGII.",
        "processes_affected": "Declaraciones mensuales 606/607/608/609/623.",
        "users_who_use_it": "Contadores, responsable fiscal, auditores.",
        "risk_activate": "Habilita generación de reportes en la empresa.",
        "risk_deactivate": "Bloquea nuevas generaciones; conserva históricos.",
        "category": "reports",
        "icon": "fa-bar-chart",
        "sequence": 30,
        "activation_scope": "company",
        "feature_flag_codes": ["dgii_reports"],
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": True,
    },
}
