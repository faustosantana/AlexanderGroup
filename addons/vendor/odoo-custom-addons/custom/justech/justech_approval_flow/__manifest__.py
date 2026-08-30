# -*- coding: utf-8 -*-
{
    "name": "Aprobaciones",
    "version": "19.0.1.3.8",
    "category": "Hidden",
    "summary": "Aprobación simple de OC, cotizaciones y facturas cliente",
    "description": """
Motor central de aprobaciones Justech (19.0.1.3.8)

- 1.3.8: Recuperar OC invalidated (to approve) — Solicitar aprobación nuevamente;
  nueva request/token; mensaje funcional token viejo; gate PDF final OC;
  bloqueo envío proveedor hasta approved; banner solicitud RFQ
- 1.3.7: Admin global (Settings / Administrador aprobaciones) puede decidir en user.company_ids; reglas por compañía para usuarios normales
- 1.3.6: Mail approve/reject requires login; CSRF kept; expired session → login → return (no auto-approve)
- Approve de venta completa la confirmación original (sin segundo Confirmar)
- Purchase UX: un solo Solicitar aprobación; Enviar al proveedor (RFQ)
- Confirmación de venta como único gate
- Envío inmediato de correo premium de aprobación
- Sin correo duplicado de actividad en solicitudes AF
- Comentario y adjuntos en la solicitud
- Bypass de administrador y autoaprobación explícita
- Factura derivada de venta aprobada no pide segunda aprobación
- Correo de resultado al solicitante
""",
    "author": "Justech",
    "website": "https://justech.do",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "purchase",
        "sale",
        "account",
        "web",
    ],
    "data": [
        "security/approval_security.xml",
        "security/ir.model.access.csv",
        "data/mail_data.xml",
        "views/approval_user_rule_views.xml",
        "views/approval_request_views.xml",
        "views/purchase_order_views.xml",
        "views/purchase_report_pending_banner.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
        "wizards/reject_wizard_views.xml",
        "wizards/approve_wizard_views.xml",
        "wizards/sale_confirm_gate_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "justech_approval_flow/static/src/js/form_request_approval_save.js",
        ],
        "web.assets_unit_tests": [
            "justech_approval_flow/static/tests/form_request_approval_save.test.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
