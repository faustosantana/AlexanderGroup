{
    "name": "Administración Doralex",
    "version": "19.0.1.0.1",
    "category": "Administration",
    "summary": "Centro de administración Doralex: estado, módulos y diagnóstico",
    "description": "Menú Administración Doralex: estado del sistema, módulos, diagnóstico y configuración. Reutiliza la clave administrativa existente. No instala la consola SaaS marcada NOT_APPLICABLE.",
    "author": "Justech",
    "website": "https://doralexgroup.cloud",
    "license": "LGPL-3",
    "depends": [
        "base",
        "justech_modules",
        "justech_alexander_base",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/doralex_admin_views.xml",
        "views/menu.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
