{
    "name": "Términos de venta por compañía",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Impide mezclar términos de cotización entre compañías",
    "description": """
Protege términos y condiciones de cotización multiempresa.

- Bloquea texto Hellenia conocido en sale.order.note / plantillas.
- Exige company_id en plantillas de cotización con contenido corporativo.
- Impide asignar plantilla de otra compañía.
- Sin textos hardcodeados de términos corporativos Justgroup (históricamente vacíos).
""",
    "author": "Justech",
    "website": "https://www.justech.com",
    "license": "LGPL-3",
    "depends": ["sale_management"],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
