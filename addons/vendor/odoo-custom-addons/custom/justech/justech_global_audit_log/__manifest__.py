{
    "name": "Auditoría",
    "version": "19.0.4.1.4",
    "category": "Productivity",
    "summary": "Trazabilidad e investigación de cambios en Odoo",
    "description": """
Herramienta de trazabilidad para cualquier cliente Odoo.

Responda quién creó, modificó o eliminó un documento, qué cambió,
cuándo ocurrió y con qué valores antes/después.

- Histórico de cambios con filtros
- Configuración por modelo, operación y empresa
- Retención automática
- Grupos de seguridad independientes
- Instalable en cualquier proyecto (depende solo de base)
    """,
    "author": "Justech",
    "website": "https://www.justech.com",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/justech_audit_security.xml",
        "security/justech_audit_rules.xml",
        "security/ir.model.access.csv",
        "data/audit_field_exclude_data.xml",
        "data/audit_retention_data.xml",
        "data/audit_cron.xml",
        "views/audit_log_views.xml",
        "views/audit_policy_views.xml",
        "views/audit_rule_views.xml",
        "views/audit_field_exclude_views.xml",
        "views/audit_user_exclude_views.xml",
        "views/audit_retention_views.xml",
        "views/audit_dashboard_views.xml",
        "views/partner_audit_button.xml",
        "wizards/audit_export_wizard_views.xml",
        "views/menu.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "justech_register": {
        "module_code": "justech_global_audit_log",
        "module_name": "Auditoría",
        "version": "19.0.4.1.4",
        "category": "platform",
        "description": "Global audit and traceability for Odoo",
        "dependencies": [],
        "always_enabled": False,
        "features": [
            {"code": "global_audit", "name": "Global Audit Log"},
        ],
    },
    "justech_admin_center": {
        "product_code": "audit",
        "functional_name": "Auditoría",
        "short_description": "Trazabilidad global y políticas de auditoría",
        "long_description": "Qué es: auditoría y cumplimiento global Justech. Para qué sirve: logs funcionales, políticas y trazabilidad. Procesos: control interno. Crítico: no. Ámbito: global/empresa. Al desactivar: deja de registrar nuevos eventos de este módulo; no borra logs.",
        "what_it_does": "Registra trazabilidad y políticas de auditoría.",
        "processes_affected": "Cumplimiento, revisión de cambios, diagnósticos.",
        "users_who_use_it": "Auditor, administrador Justech, solo lectura.",
        "risk_activate": "Habilita registro de auditoría adicional.",
        "risk_deactivate": "Deja de registrar nuevos eventos; conserva históricos.",
        "category": "audit",
        "icon": "fa-shield",
        "sequence": 50,
        "activation_scope": "global",
        "supports_activate": True,
        "supports_deactivate": True,
        "critical": False,
    },
}
