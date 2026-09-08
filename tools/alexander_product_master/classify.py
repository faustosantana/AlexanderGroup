from __future__ import annotations

import re

from .textutil import collapse

BRANDS = (
    "midea",
    "daiwa",
    "danilux",
    "tcl",
    "whirlpool",
    "dewalt",
    "truper",
    "tropical",
    "cano",
    "samsung",
    "lg",
    "hp",
    "epson",
    "canon",
    "brother",
    "hikvision",
    "discovery",
    "oster",
    "black+decker",
    "black decker",
    "makita",
    "bosch",
    "generico",
    "genérico",
)

MEAT_PHRASES = (
    "carne de res",
    "res molida",
    "res deshuesada",
    "carne de cerdo",
    "chuleta",
    "costilla de",
    "costilla ",
    "pollo",
    "pechuga",
    "muslo",
    "jamon",
    "jamón",
    "salami",
    "pescado",
    "bacalao",
    "carne de cerdo",
    "cerdo molid",
    "cerdo deshues",
)
MEAT_WORDS = (
    "chuleta",
    "pechuga",
    "muslo",
    "jamon",
    "jamón",
    "salami",
    "bacalao",
    "costilla",
)
FOOD_PHRASES = (
    "arroz",
    "habichuela",
    "azucar",
    "azúcar",
    "harina",
    "leche",
    "huevo",
    "queso",
    "aceite comestible",
    "aceite de cocina",
    "aceite vegetal",
    "pasta aliment",
    "viveres",
    "víveres",
    "spaguetti",
    "spaghetti",
    "platano",
    "plátano",
    "yuca",
    "batata",
    "ajos",
    "cebolla",
    "tomate",
    "mantequilla",
    "mayonesa",
    "ketchup",
    "salsa de tomate",
)
FOOD_EXCLUDE = (
    "acrilic",
    "acrílic",
    "3 en 1",
    "hidraulic",
    "motor",
    "engranaje",
    "pintura",
    "thinner",
    "soldar",
    "industrial",
    "lubric",
)
SERVICE_PHRASES = (
    "limpieza de",
    "instalacion de",
    "instalación de",
    "instalacion ",
    "instalación ",
    "reparacion de",
    "reparación de",
    "reparacion ",
    "reparación ",
    "mantenimiento de",
    "mantenimiento ",
    "consultoria",
    "consultoría",
    "asesoria",
    "asesoría",
    "montaje de",
    "montaje ",
    "mano de obra",
    "capacitacion",
    "capacitación",
    "transporte de",
    "alquiler de servicio",
    "servicio de",
    "trabajos de",
    "sondeo de",
    "eventos artisticos",
    "eventos artísticos",
    "cambio de",
    "desinstal",
    "desintal",
    "demolicion",
    "demolición",
    "bote de material",
    "brigada ",
    "preparacion de terreno",
    "preparación de terreno",
    "vacio a sistema",
    "vacío a sistema",
    "verificacion y",
    "verificación y",
    "intalacion",
    "desintacion",
    "desintalacion",
)
SERVICE_EXCLUDE = (
    "valvula de servicio",
    "válvula de servicio",
    "kit de servicio",
    "kit de instalacion",
    "kit de instalación",
    "tubo de servicio",
    "llave de servicio",
    "bomba de servicio",
)
COST_HINTS = (
    "analisis de costo",
    "análisis de costo",
    "costo unitario",
    "volumen analisis",
)
DELIVERY_HINTS = ("conduce", "albaran", "albarán", "entrega")
INVOICE_HINTS = ("factura", "ncf")
QUOTE_HINTS = ("cotizacion", "cotización")


def document_type(sheet_name: str, preview: str) -> str:
    blob = collapse(f"{sheet_name} {preview}")
    if not blob.strip():
        return "EMPTY"
    if any(h in blob for h in COST_HINTS) or "analisis de costo" in collapse(
        sheet_name
    ):
        return "COST_ANALYSIS"
    if any(h in blob for h in DELIVERY_HINTS):
        return "DELIVERY"
    if any(h in blob for h in INVOICE_HINTS) and "cotiz" not in collapse(sheet_name):
        if "factura" in collapse(sheet_name) or "ncf" in blob:
            return "INVOICE"
    if any(h in blob for h in QUOTE_HINTS) or "cotiz" in collapse(sheet_name):
        return "QUOTATION"
    if "descripcion" in blob and ("p.u" in blob or "precio" in blob):
        return "QUOTATION"
    if "descripcion" in blob and "cant" in blob:
        return "PRODUCT_LIST"
    return "UNKNOWN"


def is_service(text: str) -> bool:
    n = collapse(text)
    if any(
        x in n
        for x in (
            "kit de instalacion",
            "kit de instalación",
            "kit de servicio",
        )
    ) and not any(
        v in n
        for v in (
            "reparacion",
            "reparación",
            "mantenimiento",
            "limpieza",
            "mano de obra",
        )
    ):
        return False
    if any(x in n for x in SERVICE_EXCLUDE) and not any(
        v in n
        for v in (
            "instalacion",
            "instalación",
            "reparacion",
            "reparación",
            "mantenimiento",
            "limpieza",
            "cambio de",
        )
    ):
        return False
    return any(x in n for x in SERVICE_PHRASES) or n in {
        "mano de obra",
        "instalacion",
        "instalación",
        "reparacion",
        "reparación",
        "mantenimiento",
        "montaje",
        "limpieza",
        "demolicion",
        "demolición",
    }


def is_meat(text: str) -> bool:
    n = collapse(text)
    if any(x in n for x in FOOD_EXCLUDE):
        return False
    if any(x in n for x in MEAT_PHRASES):
        return True
    tokens = set(n.split())
    return bool(tokens & set(MEAT_WORDS))


def is_food(text: str) -> bool:
    if is_meat(text):
        return False
    n = collapse(text)
    if any(x in n for x in FOOD_EXCLUDE):
        return False
    if "pasta" in n and "aliment" not in n and "spag" not in n:
        return False
    if "aceite" in n and not any(
        x in n for x in ("comest", "cocina", "vegetal", "oliva", "girasol")
    ):
        return False
    return any(x in n for x in FOOD_PHRASES)


def category_for(text: str, service: bool, food: bool, meat: bool) -> str:
    if service:
        return "Servicios"
    if meat:
        return "Carnes"
    if food:
        return "Alimentos"
    n = collapse(text)
    rules = (
        ("Neumáticos", ("goma ", "neumatic", "llanta", "rin ")),
        ("Pinturas", ("pintura", "thinner", "brocha", "rodillo")),
        (
            "Electrodomésticos",
            (
                "nevera",
                "lavadora",
                "televisor",
                "tv ",
                "abanico",
                "licuadora",
                "estufa",
                "microondas",
            ),
        ),
        (
            "Tecnología",
            (
                "toner",
                "tóner",
                "laptop",
                "impresora",
                "router",
                "camara",
                "cámara",
                "monitor",
            ),
        ),
        (
            "Oficina",
            ("resma", "folder", "papel", "lapicero", "boligrafo", "archivador"),
        ),
        (
            "Mobiliario",
            ("silla", "mesa", "escritorio", "estante", "archivo metal", "sofa"),
        ),
        (
            "Plomería",
            (
                "pvc",
                "codo",
                "tee ",
                "inodoro",
                "lavamanos",
                "grifo",
                "valvula",
                "válvula",
                "tubo",
            ),
        ),
        (
            "Material eléctrico",
            (
                "cable",
                "breaker",
                "tomacorriente",
                "bombillo",
                "led",
                "tuberia emt",
                "conduit",
            ),
        ),
        (
            "Herramientas",
            (
                "taladro",
                "alicate",
                "destornillador",
                "sierra",
                "martillo",
                "truper",
                "dewalt",
            ),
        ),
        (
            "Construcción",
            (
                "cemento",
                "varilla",
                "block",
                "arena",
                "grava",
                "plywood",
                "ply wood",
                "hormigon",
                "hormigón",
            ),
        ),
        ("Limpieza", ("cloro", "detergente", "jabon", "jabón", "desinfectante")),
        (
            "Ferretería",
            ("tornillo", "clavo", "tuerca", "bisagra", "candado", "cerradura"),
        ),
    )
    for cat, keys in rules:
        if any(k in n for k in keys):
            return cat
    return "Ferretería"


def extract_brand(text: str) -> str:
    n = collapse(text)
    for brand in BRANDS:
        if brand in n:
            return brand.upper() if brand in {"hp", "lg", "tcl"} else brand.title()
    return ""


def extract_specs(text: str) -> dict:
    n = collapse(text)
    specs = {}
    inch = re.findall(r'(\d+(?:\.\d+)?)\s*(?:"|pulg|inch)', n)
    if inch:
        specs["size"] = f'{inch[0]}"'
    frac = re.findall(r"\b(\d+/\d+)\b", n)
    if frac:
        specs["caliber"] = frac[0]
    pies = re.findall(r"(\d+(?:\.\d+)?)\s*(?:pies|pie|ft)\b", n)
    if pies:
        specs["capacity"] = f"{pies[0]} pies"
    watts = re.findall(r"(\d+(?:\.\d+)?)\s*w\b", n)
    if watts:
        specs["power"] = f"{watts[0]}W"
    pack = re.findall(r"(\d+(?:\.\d+)?)\s*(kg|lb|lbs|gal|gl|m2|m3|l)\b", n)
    if pack:
        specs["presentation"] = f"{pack[0][0]} {pack[0][1]}"
    model = re.findall(r"\b([a-z]{1,4}-?[a-z0-9]{2,8}\d[a-z0-9-]*)\b", n)
    if model:
        specs["model"] = model[0].upper()
    return specs


def _split_num_unit(text: str) -> str:
    text = re.sub(
        r"(\d+(?:\.\d+)?)(kg|lb|lbs|gal|gl|m2|m3|mm|cm|mt|w)\b", r"\1 \2", text
    )
    text = re.sub(r"\blbs\b", "lb", text)
    text = re.sub(r"\bgl\b", "gal", text)
    return text


def identity_key(text: str) -> str:
    """Stable identity. Parenthetical aliases are stripped by collapse(), so
    '(AGREGADO GRUESO) GRAVA 3/4' and 'AGREGADO GRUESO (GRAVA) 3/4' match.
    """
    n = _split_num_unit(collapse(text))
    specs = extract_specs(_split_num_unit(text))
    tokens = [
        t
        for t in n.split()
        if t not in {"de", "del", "la", "el", "los", "las", "y", "en", "con"}
    ]
    spec_bits = [specs[k] for k in sorted(specs)]
    return "|".join(tokens[:8] + spec_bits)


def map_uom(raw: str) -> str:
    n = collapse(raw or "")
    mapping = {
        "ud": "Units",
        "und": "Units",
        "u": "Units",
        "unidad": "Units",
        "unidades": "Units",
        "pza": "Units",
        "pieza": "Units",
        "gl": "Gal",
        "gal": "Gal",
        "galon": "Gal",
        "galón": "Gal",
        "lb": "lb",
        "lbs": "lb",
        "libra": "lb",
        "kg": "kg",
        "m2": "m²",
        "m3": "m³",
        "m": "m",
        "mt": "m",
        "metro": "m",
        "pie": "ft",
        "pies": "ft",
        "caja": "Units",
        "paquete": "Units",
        "resma": "Units",
        "rollo": "Units",
        "saco": "Units",
        "juego": "Units",
        "par": "Units",
        "hora": "Hours",
        "dia": "Days",
        "día": "Days",
    }
    return mapping.get(n, "Units")
