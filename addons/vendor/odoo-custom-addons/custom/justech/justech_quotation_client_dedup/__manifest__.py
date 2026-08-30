{
    "name": "Evitar clientes duplicados en cotización",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Elimina el bloque duplicado de cliente en el encabezado de cotizaciones",
    "description": """
Hotfix mínimo para cotizaciones (sale.report_saleorder_document).

Anula únicamente el t-set=\"address\" que imprime doc.partner_id vía
web.address_layout debajo de los datos de la empresa.

Conserva intacto el cuadro Cliente (#informations / customer_info)
debajo del título Cotización.

No modifica layouts globales (bubble / address_layout) ni otros reportes.
    """,
    "author": "Justech",
    "website": "https://www.justech.com",
    "license": "LGPL-3",
    "depends": ["sale"],
    "data": [
        "report/sale_report_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
