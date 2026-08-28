"""Perfiles públicos y convención de nomenclatura Doralex.

Se identifican compañías por nombre comercial/legal (ya cargados en DEV),
nunca por ID numérico. No incluye RNC, cuentas, cédulas ni representantes.
"""

# Códigos de almacén: máximo 5 caracteres y únicos en toda la instancia.
COMPANY_PROFILES = (
    {
        "match": "DORALEX",
        "code": "DOR",
        "trade_name": "Doralex",
        "legal_display": "Inversiones Doralex",
        "sector": "Inversiones, comercio, agroindustria e industria",
        "description": (
            "Empresa del grupo con actividad en servicio, comercio, "
            "agroindustria e industria. Casa de referencia de Doralex Group."
        ),
        "color": "#1B365D",
        "color_secondary": "#C4A35A",
        "sequence": 10,
        "areas": ("Inversiones", "Comercio", "Agroindustria", "Industria"),
    },
    {
        "match": "PIÑARIA",
        "code": "PIN",
        "trade_name": "Piñaria",
        "legal_display": "Comercializadora de Alimentos Piñaria",
        "sector": "Alimentos, distribución e importación",
        "description": (
            "Comercializadora de alimentos con operaciones de comercio, "
            "distribución, importación y servicio al mercado dominicano."
        ),
        "color": "#2E7D32",
        "color_secondary": "#8D6E63",
        "sequence": 20,
        "areas": ("Alimentos", "Distribución", "Importación"),
    },
    {
        "match": "DOMINION",
        "code": "DOM",
        "trade_name": "Dominion",
        "legal_display": "Dominion Business",
        "sector": "Comercio y servicios",
        "description": (
            "Compañía del grupo orientada al comercio y a la prestación "
            "de servicios empresariales."
        ),
        "color": "#1565C0",
        "color_secondary": "#90A4AE",
        "sequence": 30,
        "areas": ("Comercio", "Servicios"),
    },
    {
        "match": "MAYUMA",
        "code": "MAY",
        "trade_name": "El Mayuma",
        "legal_display": "Inversiones El Mayuma",
        "sector": "Comercio, servicios e inversión",
        "description": (
            "Empresa de comercio y servicios que forma parte del portafolio "
            "de inversión del grupo."
        ),
        "color": "#6A1B9A",
        "color_secondary": "#B39DDB",
        "sequence": 40,
        "areas": ("Inversión", "Comercio", "Servicios"),
    },
    {
        "match": "REMPART",
        "code": "REM",
        "trade_name": "Rempart",
        "legal_display": "Rempart Group",
        "sector": "Comercio y servicios",
        "description": (
            "Grupo comercial de servicios que opera de forma independiente "
            "dentro de Doralex Group."
        ),
        "color": "#C62828",
        "color_secondary": "#BCAAA4",
        "sequence": 50,
        "areas": ("Comercio", "Servicios"),
    },
    {
        "match": "BLUE ELITE",
        "code": "BLU",
        "trade_name": "Blue Elite",
        "legal_display": "Blue Elite",
        "sector": "Comercio y servicios",
        "description": (
            "Compañía de comercio y servicios del grupo, con identidad "
            "propia y operación independiente."
        ),
        "color": "#0D47A1",
        "color_secondary": "#90CAF9",
        "sequence": 60,
        "areas": ("Comercio", "Servicios"),
    },
)

JOURNAL_LABELS = {
    "sale": "Ventas",
    "purchase": "Compras",
    "bank": "Banco Banreservas",
    "cash": "Caja Principal",
    "general": None,
}

GENERAL_JOURNAL_HINTS = (
    ("EXCH", "Diferencia de cambio"),
    ("CABA", "Impuestos base caja"),
    ("STJ", "Valoración de inventario"),
    ("MISC", "Operaciones diversas"),
)

PICKING_LABELS = {
    "incoming": "Recepción",
    "outgoing": "Entrega",
    "internal": "Transferencia interna",
}

LOCATION_LABELS = {
    "Stock": "Existencias",
    "Input": "Entrada",
    "Output": "Salida",
    "Quality Control": "Control de calidad",
    "Packing Zone": "Zona de empaque",
}

PUBLIC_PAYLOAD_KEYS = (
    "id",
    "code",
    "trade_name",
    "legal_display",
    "sector",
    "description",
    "color",
    "logo_url",
    "sequence",
    "areas",
)


def profile_for_company(company):
    name = (company.name or "").upper()
    for profile in COMPANY_PROFILES:
        if profile["match"] in name:
            return profile
    return None


def all_business_areas():
    seen = []
    for profile in COMPANY_PROFILES:
        for area in profile["areas"]:
            if area not in seen:
                seen.append(area)
    return seen
