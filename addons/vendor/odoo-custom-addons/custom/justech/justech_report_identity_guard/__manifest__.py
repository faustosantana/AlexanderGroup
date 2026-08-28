{
    "name": "Justech Report Identity Guard",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Fail-closed: no cross-company / Hellenia report template substitution",
    "description": """
Guarda permanente de identidad gráfica multiempresa (Justgroup ERP).

Reglas:
- Las acciones oficiales de impresión deben apuntar a plantillas Odoo estándar
  (sale / account / stock / purchase), no a justech_report_design / hellenia_*.
- La identidad por empresa es logo + external_layout (Studio), nunca reutilizar
  plantillas de otra marca.
- Si una plantilla oficial falta o se intenta redirigir a Hellenia: error de
  configuración (fail-closed). Nunca sustituir automáticamente.
""",
    "author": "Justech",
    "website": "https://www.justech.com",
    "license": "LGPL-3",
    "depends": ["sale", "account", "stock", "purchase"],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
