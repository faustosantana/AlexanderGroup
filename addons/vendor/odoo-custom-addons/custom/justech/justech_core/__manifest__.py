{
    "name": "Utilidades internas",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "summary": "Utilidades compartidas de los módulos internos",
    "description": """
Shared utilities for Justech Odoo modules

Skeleton module — no business logic yet.
See README.md for development guidelines.
    """,
    "author": "Justech",
    "website": "https://hellenia.cloud",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "justech_register": {
        "module_code": "justech_core",
        "module_name": "Justech Core",
        "version": "19.0.1.0.0",
        "category": "platform",
        "country": "",
        "localization": "",
        "description": "Shared utilities for Justech Odoo modules",
        "dependencies": [],
        "always_enabled": True,
        "features": [
            {"code": "justech_core", "name": "Justech Core Utilities"},
        ],
    },
}
