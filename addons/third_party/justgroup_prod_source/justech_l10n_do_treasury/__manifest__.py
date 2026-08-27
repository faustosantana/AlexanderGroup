{
    "name": "Justech Tesorería Dominicana",
    "version": "19.0.1.6.7",
    "category": "Accounting/Localizations",
    "summary": "Pagos abiertos, anticipos y experiencia de tesorería (aditivo, no destructivo)",
    "description": """
Tesorería Dominicana (Justech)
==============================
Módulo ADITIVO sobre el wizard de pagos Justech (justech.payment.partner.wizard).

- Modal XL responsive del wizard de pagos.
- Tipo de operación simplificado: Aplicar a factura / Registrar pago abierto.
- Menú Pagos abiertos (clientes y proveedores).
- Alerta en facturas con pagos abiertos del contacto.
- Wizard de aplicación posterior (solo conciliación, sin alterar contabilidad base).

No toca NCF, DGII, COA, retenciones ni el motor fiscal. Compatible con Framework Justech.
    """,
    "author": "Justech",
    "website": "https://hellenia.cloud",
    "depends": [
        "account",
        "account_accountant",
        "accountant",
        "justech_l10n_do_payments_withholding",
        "justech_l10n_do_reports",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hide_duplicate_payment_menus.xml",
        "views/payment_partner_wizard_views.xml",
        "views/account_payment_open_views.xml",
        "views/account_payment_bank_ux_views.xml",
        "views/account_move_open_payment_alert_views.xml",
        "views/treasury_apply_wizard_views.xml",
        "views/menu_accounting_navigation.xml",
        "data/menu_accounting_order.xml",
    ],
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_backend": [
            "justech_l10n_do_treasury/static/src/scss/treasury.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_l10n_do_treasury",
        "module_name": "Tesorería Dominicana",
        "version": "19.0.1.6.7",
        "category": "treasury",
        "country": "DO",
        "description": "Pagos abiertos y experiencia de tesorería",
        "dependencies": ["justech_l10n_do_payments_withholding"],
        "always_enabled": True,
        "features": [{"code": "treasury_rd", "name": "Tesorería RD"}],
    },
    "justech_admin_center": {
        "product_code": "finance",
        "functional_name": "Tesorería",
        "short_description": "Pagos abiertos, anticipos y aplicación a facturas",
        "long_description": "Qué es: módulo de tesorería operativa. Para qué sirve: pagos abiertos, anticipos y aplicación. Procesos: liquidez y conciliación. Datos: pagos, facturas abiertas. Crítico: no. Ámbito: por empresa. Al desactivar: oculta menús nuevos; conserva históricos.",
        "what_it_does": "Gestiona pagos abiertos y aplicación a facturas.",
        "processes_affected": "Tesorería, anticipos, aplicación de pagos.",
        "users_who_use_it": "Administrador de tesorería, usuario de tesorería.",
        "risk_activate": "Habilita operaciones de tesorería en la empresa.",
        "risk_deactivate": "Bloquea nuevas operaciones; conserva lectura e histórico.",
        "category": "treasury",
        "icon": "fa-bank",
        "sequence": 45,
        "activation_scope": "company",
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": False,
    },
}
