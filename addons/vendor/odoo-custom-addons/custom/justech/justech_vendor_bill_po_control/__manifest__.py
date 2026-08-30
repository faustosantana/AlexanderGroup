# -*- coding: utf-8 -*-
{
    "name": "Control de facturas proveedor / OC",
    "version": "19.0.3.6.2",
    "category": "Accounting/Localizations",
    "summary": "OC automática o aprobación; contabilización al aprobar; bandeja única",
    "description": """
Control definitivo de OC en facturas de proveedor
=================================================

- Con OC válida: Confirmar estándar (action_post).
- Sin OC: solo Enviar a aprobación; al aprobar → action_post automático.
- Si faltan datos fiscales: alerta clara + Confirmar sin nueva aprobación.
- Clasificación automática Compra directa / Gasto interno.
- Bandeja única en Contabilidad → Proveedores.
- Actividades mail.activity para futuro Centro de Trabajo.
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "account",
        "purchase",
        "mail",
        "justech_l10n_do_ncf",
    ],
    "data": [
        "security/po_control_security.xml",
        "security/ir.model.access.csv",
        "data/po_exception_category_data.xml",
        "data/mail_data.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/po_exception_rule_views.xml",
        "views/account_move_views.xml",
        "wizards/approval_wizard_views.xml",
        "views/menu.xml",
        "report/vendor_bill_po_report.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
}
