{
    "name": "Justech Dominican NCF",
    "version": "19.0.2.31.0",
    "category": "Accounting/Localizations",
    "summary": "NCF ranges, assignment and validation (Dominican Republic)",
    "description": """
NCF management for Dominican Republic — Justech Enterprise layer.

- NCF ranges and consumption audit
- Automatic NCF on customer invoices
- Fiscal Administration Center
- Unified Corregir o Anular (NC + cancelación directa NCF no entregado)
- Centro de regularización fiscal (608 / rectificativas)
- Separate Anular NCF vs Revertir factura (Option C; botones legacy ocultos en UI)
- UX fiscal: permisos claros en Corregir o Anular; Centro de Rangos 1-clic
- Reverse & replace context fix (Odoo 19)
- Vendor CN data on standard reversal wizard
- e-CF gate via Justech e-CF document states (lab/DEV; no real DGII transmit)
- Fiscal diagnostic (read-only)
- Controlled migration legacy → Justech
- Post-sync NCF reconcile
- Duplicate detection v2.0
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "justech_l10n_do_base",
        "mail",
        "account_debit_note",
        "sale",
        "purchase",
        "sale_purchase",
        "bi_convert_purchase_from_sales",
        "justech_accounting_recovery",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/justech_l10n_do_ncf_rules.xml",
        "data/ncf_range_alert_data.xml",
        "views/fiscal_admin_views.xml",
        "views/fiscal_diagnostic_views.xml",
        "views/ncf_range_views.xml",
        "views/ncf_consumption_views.xml",
        "views/ncf_migration_views.xml",
        "views/purchase_emission_config_views.xml",
        "views/purchase_received_type_views.xml",
        "views/fiscal_range_center_views.xml",
        "views/purchase_order_ux_views.xml",
        "views/account_move_views.xml",
        "views/ncf_void_wizard_views.xml",
        "views/invoice_correct_wizard_views.xml",
        "views/res_company_views.xml",
        "views/fiscal_regularization_views.xml",
        "views/fiscal_dashboard_views.xml",
        "views/fiscal_historical_backfill_views.xml",
        "views/account_move_reversal_views.xml",
        "views/sale_order_views.xml",
        "views/menu.xml",
        "report/report_invoice.xml",
        "report/report_invoice_l10n_do_gate.xml",
        "report/report_invoice_currency_and_ncf_validity.xml",
        "report/report_invoice_ncf_sot.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
    "justech_register": {
        "module_code": "justech_l10n_do_ncf",
        "module_name": "Justech Dominican NCF",
        "version": "19.0.2.31.0",
        "category": "fiscal",
        "country": "DO",
        "localization": "l10n_do",
        "description": "NCF + Corregir o Anular (auth via can_recover_accounting_document)",
        "dependencies": ["justech_l10n_do_base"],
        "always_enabled": True,
        "required_module": True,
        "features": [
            {"code": "l10n_do_ncf", "name": "DO NCF Management"},
            {"code": "l10n_do_ncf_admin", "name": "DO Fiscal Admin Center"},
        ],
    },
    "justech_admin_center": {
        "product_code": "fiscal",
        "functional_name": "Motor NCF",
        "short_description": "Rangos, asignación y diagnóstico NCF",
        "long_description": "Qué es: motor de comprobantes fiscales NCF. Para qué sirve: asignar, controlar rangos y diagnosticar. Procesos: facturas de cliente/proveedor. Datos: secuencias NCF, tipos y consumo. Crítico: sí. Ámbito: por empresa. Al activar: permite emitir con motor tradicional o electrónico según empresa. Al desactivar: bloquea nuevas asignaciones; conserva NCF emitidos. Depende de: base fiscal.",
        "what_it_does": "Gestiona rangos y asignación de NCF por empresa.",
        "processes_affected": "Emisión de facturas, notas de crédito y compras con NCF.",
        "users_who_use_it": "Facturación, compras, contabilidad, responsable fiscal.",
        "risk_activate": "Habilita asignación de NCF en la empresa.",
        "risk_deactivate": "Impide nuevas asignaciones; no altera NCF históricos.",
        "category": "fiscal",
        "icon": "fa-file-text-o",
        "sequence": 20,
        "activation_scope": "company",
        "fiscal_engine_capable": True,
        "feature_flag_codes": ["ncf_motor"],
        "health_method": "justech.do.ncf.diagnostic.service.run_full_scan",
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": True,
    },
}
