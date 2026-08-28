# -*- coding: utf-8 -*-
{
    "name": "Justech Contabilidad — Recuperación Contable (SoD)",
    "version": "19.0.1.4.0",
    "category": "Accounting/Accounting",
    "summary": "Segregación de funciones: Recuperación Contable + autorización consolidada",
    "description": """
Endurecimiento de seguridad contable (P2).

Crea el grupo «Recuperación Contable» y exige membresía explícita para
ejecutar acciones de restablecimiento, cancelación, reversión y
eliminación (unlink) de account.move / account.payment.

Autorización consolidada (19.0.1.4.0):
``res.users.can_recover_accounting_document(company)`` — fuente única para
Corregir o Anular / recuperación por empresa (roles superiores incluidos).
Sin implied_ids globales (evita ampliar SoD draft/cancel fuera del flujo).
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": ["account"],
    "data": [
        "security/accounting_recovery_security.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/account_move_reversal_views.xml",
    ],
    "uninstall_hook": "uninstall_hook",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "justech_register": {
        "module_code": "justech_accounting_recovery",
        "module_name": "Justech Recuperación Contable",
        "version": "19.0.1.4.0",
        "category": "accounting",
        "country": "DO",
        "description": "SoD Recuperación Contable + can_recover_accounting_document",
        "dependencies": ["account"],
        "always_enabled": False,
        "required_module": False,
    },
}
