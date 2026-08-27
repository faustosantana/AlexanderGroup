# -*- coding: utf-8 -*-
{
    "name": "Justech Adel Freeze (Dual-Engine Gate)",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Freeze Adel NCF emission when Justech fiscal motor is enabled",
    "description": """
Bridge module: keeps l10n_do_accounting installed for historical read (FDP)
but blocks Adel sequence consumption and auto-assignment on new documents
when the company has justech_do_fiscal_enabled.

- Does NOT uninstall Adel
- Does NOT backfill NCF
- Does NOT reactivate l10n_latam_use_documents
- Dual-write remains Justech → l10n_latam_document_number only
    """,
    "author": "Justech",
    "website": "https://justech.do",
    "depends": [
        "justech_l10n_do_ncf",
        "l10n_do_accounting",
    ],
    "data": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_l10n_do_adel_freeze",
        "module_name": "Justech Adel Freeze",
        "version": "19.0.1.0.0",
        "category": "fiscal",
        "country": "DO",
        "localization": "l10n_do",
        "description": "Freeze Adel emission; Justech sole write motor",
        "dependencies": ["justech_l10n_do_ncf", "l10n_do_accounting"],
        "features": [
            {"code": "adel_freeze", "name": "Adel Freeze Dual-Engine Gate"},
        ],
    },
}
