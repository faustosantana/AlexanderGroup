"""Semantic product nature for the Alexander catalog (Odoo 19).

Does not invent inventory. Goods = type 'consu' + is_storable False unless
a separate inventory policy exists. Services stay type 'service'.
"""

from __future__ import annotations

from .classify import category_for, is_food, is_meat, is_service
from .textutil import collapse

GOODS_TYPE = "consu"
SERVICE_TYPE = "service"

PROFESSIONAL_SERVICE_NAMES = {
    "servicios profesionales",
    "servicio profesional",
}

ODOO_SYSTEM_SERVICES = {
    "event registration",
    "field service",
    "service on timesheets",
    "servicio de verificacion interna",
    "servicio de verificación interna",
}

KEEP_SERVICE_PHRASES = (
    "caja chica",
    "cubicacion",
    "cubicación",
    "peaje",
    "bote material",
    "bote de material",
    "corte, carga",
    "corte y carga",
    "transporte caliche",
    "traslado y regado",
    "servicio material caliche",
    "rampa de acceso",
    "horas fuera de proyecto",
    "mano de obra",
    "servicios profesionales",
)

AMBIGUOUS_KEEP_PHRASES = (
    "apertura historica",
    "apertura histórica",
)

# Physical materials / merchandise. Order matters vs isolated "servicio".
PHYSICAL_PHRASES = (
    "agregado fino",
    "agregado grueso",
    "arena lavada",
    "grava",
    "cemento",
    "varilla",
    "hormigon",
    "hormigón",
    "plywood",
    "disco de corte",
    "pinza de corte",
    "pinza de extension",
    "pinza de extensión",
    "pinza lagarto",
    "kit de instalacion",
    "kit de instalación",
    "valvula de servicio",
    "válvula de servicio",
    "toner",
    "tóner",
    "nevera",
    "lavadora",
    "televisor",
    "licuadora",
    "microonda",
    "abanico",
    "estufa",
    "taladro",
    "alicate",
    "destornillador",
    "pintura",
    "thinner",
    "breaker",
    "alambre",
    "cable ",
    "tubo ",
    "tornillo",
    "inodoro",
    "orinal",
    "lavamanos",
    "neumatic",
    "goma ",
    "carne de",
    "res molida",
    "res deshuesada",
    "chuleta",
    "pollo",
    "arroz",
    "habichuela",
    "leche",
)


def _is_professional(name: str) -> bool:
    return collapse(name) in PROFESSIONAL_SERVICE_NAMES


def _is_system_service(name: str) -> bool:
    return collapse(name) in {collapse(x) for x in ODOO_SYSTEM_SERVICES}


def _has_phrase(name: str, phrases: tuple[str, ...] | set[str]) -> bool:
    n = collapse(name)
    return any(collapse(p) in n for p in phrases)


def is_physical_good(name: str) -> bool:
    if _is_professional(name) or _is_system_service(name):
        return False
    if _has_phrase(name, KEEP_SERVICE_PHRASES):
        return False
    if _has_phrase(name, AMBIGUOUS_KEEP_PHRASES):
        return False
    if is_food(name) or is_meat(name):
        return True
    if _has_phrase(name, PHYSICAL_PHRASES):
        return True
    if is_service(name):
        return False
    return False


def classify_nature(
    name: str,
    *,
    current_type: str = "",
    category: str = "",
    active: bool = True,
    sale_ok: bool = True,
    purchase_ok: bool = True,
) -> dict:
    """Return proposed nature, flags, confidence and action. Never deletes."""
    n = collapse(name)
    current_type = current_type or ""
    proposed_sale = True if sale_ok or is_physical_good(name) else sale_ok
    proposed_purchase = purchase_ok
    confidence = "HIGH_CONFIDENCE"
    nature = "PHYSICAL_GOOD"
    reason = ""
    mismatch = ""

    if _is_professional(name) or _is_system_service(name):
        nature = "SERVICE"
        confidence = "DETERMINISTIC"
        proposed_sale = True if _is_professional(name) else sale_ok
        proposed_purchase = purchase_ok
        reason = "Canonical or system service; keep type=service"
    elif _has_phrase(name, KEEP_SERVICE_PHRASES) or (
        is_service(name) and not _has_phrase(name, PHYSICAL_PHRASES)
    ):
        nature = "SERVICE"
        confidence = "HIGH_CONFIDENCE" if not is_service(name) else "DETERMINISTIC"
        if _has_phrase(name, KEEP_SERVICE_PHRASES):
            confidence = "HIGH_CONFIDENCE"
            reason = "Construction/haulage/petty-cash activity, not a SKU"
        else:
            reason = "Service phrase in full name"
        proposed_sale = sale_ok
        proposed_purchase = purchase_ok
    elif _has_phrase(name, AMBIGUOUS_KEEP_PHRASES):
        nature = "AMBIGUOUS"
        confidence = "AMBIGUOUS"
        proposed_sale = sale_ok
        proposed_purchase = purchase_ok
        reason = "Opening placeholder / non-SKU; do not auto-correct"
    elif is_food(name) or is_meat(name) or _has_phrase(name, PHYSICAL_PHRASES):
        nature = "PHYSICAL_GOOD"
        confidence = "DETERMINISTIC"
        proposed_sale = True
        proposed_purchase = True
        reason = "Physical material, merchandise, food or tool"
    elif current_type == GOODS_TYPE and not is_service(name):
        nature = "PHYSICAL_GOOD"
        confidence = "HIGH_CONFIDENCE"
        proposed_sale = True
        proposed_purchase = True
        reason = "Already Goods and name is not a service"
    elif current_type == SERVICE_TYPE:
        nature = "AMBIGUOUS"
        confidence = "AMBIGUOUS"
        proposed_sale = sale_ok
        proposed_purchase = purchase_ok
        reason = "Service type without a deterministic nature rule"
    else:
        nature = "PHYSICAL_GOOD"
        confidence = "HIGH_CONFIDENCE"
        proposed_sale = True
        proposed_purchase = True
        reason = "Default catalog good (quotation merchandise)"

    proposed_type = SERVICE_TYPE if nature == "SERVICE" else GOODS_TYPE
    if nature == "AMBIGUOUS":
        proposed_type = current_type or GOODS_TYPE

    if current_type == SERVICE_TYPE and nature == "PHYSICAL_GOOD":
        mismatch = "PHYSICAL_AS_SERVICE"
    elif current_type == GOODS_TYPE and nature == "SERVICE":
        mismatch = "SERVICE_AS_PHYSICAL"
    elif current_type == GOODS_TYPE and nature == "PHYSICAL_GOOD":
        mismatch = ""
    elif current_type == SERVICE_TYPE and nature == "SERVICE":
        mismatch = ""

    if not active:
        action = "KEEP_ARCHIVED"
        writable = False
        reason = (reason + "; archived — do not reactivate").strip("; ")
    elif nature == "AMBIGUOUS":
        action = "MANUAL_REVIEW"
        writable = False
    elif confidence == "AMBIGUOUS":
        action = "MANUAL_REVIEW"
        writable = False
    else:
        type_fix = current_type != proposed_type
        sale_fix = bool(sale_ok) != bool(proposed_sale)
        purchase_fix = bool(purchase_ok) != bool(proposed_purchase)
        writable = type_fix or sale_fix or purchase_fix
        if type_fix and (sale_fix or purchase_fix):
            action = "FIX_TYPE_AND_FLAGS"
        elif type_fix:
            action = "FIX_TYPE"
        elif sale_fix and purchase_fix:
            action = "FIX_SALE_AND_PURCHASE_OK"
        elif purchase_fix:
            action = "FIX_PURCHASE_OK"
        elif sale_fix:
            action = "FIX_SALE_OK"
        else:
            action = "KEEP"

    return {
        "NATURE": nature,
        "CURRENT_TYPE": current_type,
        "PROPOSED_TYPE": proposed_type,
        "PROPOSED_SALE_OK": bool(proposed_sale),
        "PROPOSED_PURCHASE_OK": bool(proposed_purchase),
        "PROPOSED_IS_STORABLE": False,
        "CONFIDENCE": confidence,
        "MISMATCH": mismatch,
        "ACTION": action,
        "WRITABLE": writable and action != "KEEP_ARCHIVED",
        "REASON": reason,
        "CATEGORY_HINT": category
        or category_for(name, nature == "SERVICE", is_food(name), is_meat(name)),
        "NORMALIZED": n,
    }
