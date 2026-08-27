{
    "name": "Justech Security UX — Permisos",
    "version": "19.0.4.1.9",
    "category": "Administration",
    "summary": "Única pestaña Permisos: editor visual directo de res.users.group_ids",
    "description": """
Pestaña única «Permisos» sobre grupos Odoo reales.
Cada acción escribe (4)/(3) en group_ids. Sin campos espejo ni sincronizadores.
La matriz técnica nativa se oculta de la ficha; Grupos vía menú técnico.
19.0.4.1.9: pestaña Empresas (company_id / company_ids) visible para admin.
19.0.4.1.8: coerce color_scheme=false from Usuarios→Nuevo web_save.
19.0.4.1.7: default color_scheme on res.users.settings create (new-user Guardar).
19.0.4.1.6: CREATE MODE — catálogo + pending state; apply after save.
19.0.4.1.5: new-user form — no infinite «Cargando permisos…».
19.0.4.1.4: Costos y Márgenes — caps granulares + presets por nivel.
19.0.4.1.3: sección Costos y Márgenes (Usuario/Responsable/Administrador).
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "base",
        "account",
        "purchase",
        "sale",
        "stock",
        "crm",
        "hr",
        "l10n_do_accounting",
        "justech_l10n_do_base",
        "justech_fiscal_admin",
        "justech_ecf_core",
        "justech_l10n_do_payments_withholding",
        "justech_warranty",
        "justech_admin_center",
    ],
    "data": [
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_security_ux/static/src/scss/operational_permissions.scss",
            "justech_security_ux/static/src/xml/permissions_nav.xml",
            "justech_security_ux/static/src/js/permissions_nav.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_security_ux",
        "module_name": "Justech Security UX",
        "version": "19.0.4.1.9",
        "category": "platform",
        "country": "DO",
        "description": "Permisos + Empresas (company_id / company_ids)",
        "dependencies": ["justech_admin_center", "justech_l10n_do_base"],
        "always_enabled": False,
        "required_module": False,
    },
}
