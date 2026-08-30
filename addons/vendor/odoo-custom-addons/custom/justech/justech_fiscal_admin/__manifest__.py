{
    "name": "Administración Fiscal",
    "version": "19.0.1.10.0",
    "summary": "Roles, salud fiscal, banderas y padrón DGII",
    "description": """
Centro de Administración Fiscal Justech (Enterprise).

- Roles: Usuario / Responsable / Administrador Fiscal
- Health check detallado multiempresa
- Feature flags y padrón DGII
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "base_setup",
        "justech_l10n_do_base",
        "justech_l10n_do_ncf",
    ],
    "data": [
        "security/justech_fiscal_admin_security.xml",
        "security/justech_fiscal_admin_rules.xml",
        "security/ir.model.access.csv",
        "data/justech_fiscal_feature_flag_data.xml",
        "views/justech_fiscal_admin_center_views.xml",
        "views/justech_fiscal_feature_flag_views.xml",
        "views/justech_fiscal_health_issue_views.xml",
        "views/justech_res_config_settings_views.xml",
        "views/res_users_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_fiscal_admin/static/src/scss/fiscal_admin.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_fiscal_admin",
        "module_name": "Justech Fiscal Administration Center",
        "version": "19.0.1.10.0",
        "country": "DO",
        "description": "Enterprise fiscal administration center",
        "dependencies": ["justech_l10n_do_base", "justech_l10n_do_ncf"],
        "features": [
            {"code": "fiscal_admin_center", "name": "Fiscal Admin Center"},
            {"code": "fiscal_feature_flags", "name": "Fiscal Feature Flags"},
        ],
    },
    "justech_admin_center": {
        "product_code": "fiscal",
        "functional_name": "Centro Fiscal",
        "short_description": "Administración fiscal, roles, health y padrón DGII",
        "long_description": "Qué es: consola operativa del ecosistema fiscal. Para qué sirve: administrar NCF, reportes DGII, roles fiscales y diagnóstico. Procesos: facturación, compras, declaraciones. Crítico: sí. Ámbito: por empresa. Al activar: habilita menús y operaciones fiscales. Al desactivar: bloquea nuevas operaciones sin borrar histórico. Depende de: Motor NCF y base fiscal.",
        "what_it_does": "Centraliza la administración fiscal diaria y el diagnóstico.",
        "processes_affected": "Facturación, compras, NCF, reportes 606/607 y roles fiscales.",
        "users_who_use_it": "Administrador fiscal, responsable fiscal, contadores.",
        "risk_activate": "Habilita operaciones fiscales nuevas en las empresas seleccionadas.",
        "risk_deactivate": "Bloquea nuevas emisiones; conserva histórico y lectura.",
        "category": "fiscal",
        "icon": "fa-university",
        "sequence": 10,
        "activation_scope": "company",
        "fiscal_engine_capable": True,
        "feature_flag_codes": ["ncf_motor", "dgii_reports"],
        "open_action_xmlid": "justech_fiscal_admin.action_justech_fiscal_admin_center_server",
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": True,
    },
}
