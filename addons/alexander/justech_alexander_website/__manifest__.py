{
    "name": "Doralex Website Institucional",
    "version": "19.0.1.0.3",
    "category": "Website",
    "summary": "Sitio institucional público de Doralex Group",
    "description": "Home, empresas, áreas de negocio, valores y contacto. Solo información pública: nombre comercial, logo, sector y descripción breve.",
    "author": "Justech",
    "website": "https://doralexgroup.cloud",
    "license": "LGPL-3",
    "depends": ["website", "justech_alexander_base"],
    "data": [
        "data/website_data.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "justech_alexander_website/static/src/css/doralex.css",
        ]
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
