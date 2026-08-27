{
    "name": "Justech Pagos y Retenciones Dominicanas",
    "version": "19.0.1.7.2",
    "category": "Accounting/Localizations",
    "summary": "Pagos con retenciones fiscales dominicanas (ITBIS/ISR), 623 y trazabilidad",
    "description": """
Pagos y Retenciones Dominicanas (Justech)
==========================================

- 19.0.1.7.2: Registrar pago/cobro sobre N facturas del mismo partner crea
  1 account.payment (group_payment forzado desde justech.payment.partner.wizard).
- 19.0.1.7.1: company.config lookup uses controlled sudo + with_company(account)
  so multi-company UI selection cannot hide a valid document-company retention.

Motor estándar Justech para pagos con retención fiscal:

- Wizard unificado de cobro/pago con retenciones integradas desde un solo lugar.
- Catálogo configurable vinculado a impuestos l10n_do existentes.
- Resolución contable fail-closed vía company.config (_get_withholding_account).
- Asiento de pago + líneas de retención + conciliación automática.
- Trazabilidad factura ↔ pago ↔ retención.
- Compatible con reportes DGII 606/607/623.
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "account",
        "account_accountant",
        "justech_l10n_do_base",
        "justech_l10n_do_ncf",
        "justech_l10n_do_reports",
    ],
    "data": [
        "security/justech_payments_security.xml",
        "security/ir.model.access.csv",
        "security/justech_payments_rules.xml",
        "data/legacy_payment_menus.xml",
        "views/justech_withholding_catalog_views.xml",
        "views/payment_partner_wizard_views.xml",
        "views/account_payment_register_views.xml",
        "views/account_payment_withholding_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_l10n_do_payments_withholding",
        "module_name": "Pagos y Retenciones Dominicanas",
        "version": "19.0.1.7.0",
        "category": "accounting",
        "country": "DO",
        "localization": "l10n_do",
        "description": (
            "Gestión de pagos con retenciones fiscales dominicanas, ITBIS retenido, "
            "ISR retenido, conciliación y trazabilidad fiscal."
        ),
        "dependencies": ["justech_l10n_do_ncf", "justech_l10n_do_reports"],
        "always_enabled": True,
        "required_module": False,
        "features": [
            {
                "code": "payments_withholding_rd",
                "name": "Pagos y Retenciones Dominicanas",
            }
        ],
    },
    "justech_admin_center": {
        "product_code": "fiscal",
        "functional_name": "Pagos y Retenciones",
        "short_description": "Pagos con retenciones ITBIS/ISR y conciliación",
        "long_description": "Qué es: capacidad transversal de pagos con retenciones. Para qué sirve: registrar pagos, retenciones ITBIS/ISR y conciliar. Procesos: cuentas por pagar/cobrar. Compartida entre Fiscal y Finanzas. Crítico: sí. Ámbito: por empresa. Al desactivar: bloquea nuevos pagos con retención; conserva históricos.",
        "what_it_does": "Opera pagos y retenciones ITBIS/ISR.",
        "processes_affected": "Pagos a proveedores/clientes, retenciones, conciliación.",
        "users_who_use_it": "Tesorería, cuentas por pagar, contabilidad.",
        "risk_activate": "Habilita flujo de pagos con retención.",
        "risk_deactivate": "Bloquea nuevos pagos con retención; no borra históricos.",
        "category": "payments",
        "icon": "fa-money",
        "sequence": 40,
        "activation_scope": "company",
        "feature_flag_codes": ["payments_withholding"],
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": True,
    },
}
