"""Normalización de RNC, NCF, nombres y montos. Sin inventar datos."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

NCF_RE = re.compile(r"\b([BE])(\d{2})(\d{8})\b", re.I)
MONEY_RE = re.compile(r"[-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|[-+]?\d+(?:[.,]\d{2})")


def strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def norm_name(value: str) -> str:
    return collapse_ws(strip_accents(value).upper())


def norm_vat(value: Any) -> str:
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits


def display_vat(digits: str) -> str:
    """Presentación dominicana habitual; el match siempre usa digits."""
    d = norm_vat(digits)
    if len(d) == 9:
        return f"{d[0:3]}-{d[3:8]}-{d[8]}"
    if len(d) == 11:
        return f"{d[0:3]}-{d[3:10]}-{d[10]}"
    return d


def norm_ncf(value: Any) -> str:
    if value is None:
        return ""
    raw = re.sub(r"\s+", "", str(value).upper())
    raw = raw.replace("-", "").replace(".", "")
    m = NCF_RE.search(raw)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    if re.fullmatch(r"[BE]\d{10}", raw):
        return raw
    return raw


def ncf_prefix(ncf: str) -> str:
    n = norm_ncf(ncf)
    return n[:3] if len(n) >= 3 else n


def ncf_seq(ncf: str) -> int | None:
    n = norm_ncf(ncf)
    if len(n) == 11 and n[3:].isdigit():
        return int(n[3:])
    return None


def money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = str(value).strip()
    text = text.replace("RD$", "").replace("$", "").replace(" ", "")
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(",") > 0 and text.count(".") > 0:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0")


def parse_money_in_text(text: str) -> Decimal | None:
    matches = MONEY_RE.findall(text or "")
    if not matches:
        return None
    return money(matches[-1])


COMPANY_ALIASES = {
    "INVERSIONES DORALEX": "INVERSIONES DORALEX,S.RL.",
    "INVERSIONES DORALEX,S.RL.": "INVERSIONES DORALEX,S.RL.",
    "INVERSIONES DORALEX, SRL": "INVERSIONES DORALEX,S.RL.",
    "INVERSIONES DORALEX SRL": "INVERSIONES DORALEX,S.RL.",
    "COMERCIALIZADORA DE ALIMENTOS PINARIA": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
    "COMERCIALIZADORA DE ALIMENTOS PIÑARIA": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
    "DOMINION BUSINESS": "DOMINION BUSINESS,S.R.L.",
    "INVERSIONES EL MAYUMA": "INVERSIONES EL MAYUMA, S.R.L.",
    "REMPART GROUP": "REMPART GROUP S.R.L.",
    "REMPART GROUP SRL": "REMPART GROUP S.R.L.",
    "REMPART GROUP S.R.L.": "REMPART GROUP S.R.L.",
    "BLUE ELITE": "BLUE ELITE, S.R.L.",
}

PARTNER_ALIASES = {
    "DIE": "DIRECCION DE INFRAESTRUCTURA ESCOLAR (DIE)",
    "DIRECCION INFRAESTRUCTURAL (DIE)": "DIRECCION DE INFRAESTRUCTURA ESCOLAR (DIE)",
    "DIRECCION DE INFRAESTRUCTURA ESCOLAR (DIE)": "DIRECCION DE INFRAESTRUCTURA ESCOLAR (DIE)",
    "PROPEEP": "PROYECTOS ESTRATEGICOS Y ESPECIALES DE LA PRESIDENCIA (PROPEEP)",
    "ASDE": "AYUNTAMIENTO SANTO DOMINGO ESTE (ASDE)",
    "AYUNTAMIENTO SANTO DOMINGO ESTE": "AYUNTAMIENTO SANTO DOMINGO ESTE (ASDE)",
    "AGROWILSON, S.R.L.": "AGRO WILSON, SRL",
    "AGRO WILSON, SRL": "AGRO WILSON, SRL",
    "MINISTERIO DE TRABAJO": "MINISTERIO DE TRABAJO",
}


def canon_company(name: str) -> str:
    key = norm_name(name).replace(",", "").replace(".", "")
    key = re.sub(r"\s+S\s*R\s*L$", "", key).strip()
    for alias, canon in COMPANY_ALIASES.items():
        if norm_name(alias).replace(",", "").replace(".", "").startswith(key[:20]):
            return canon
        if key.startswith(norm_name(alias).replace(",", "").replace(".", "")[:20]):
            return canon
    return collapse_ws(name)


def canon_partner(name: str) -> str:
    n = norm_name(name)
    for alias, canon in PARTNER_ALIASES.items():
        if n == norm_name(alias) or n.startswith(norm_name(alias)):
            return canon
    return collapse_ws(name)


UOM_MAP = {
    "UND": "Units",
    "UNIDAD": "Units",
    "UD": "Units",
    "U": "Units",
    "M3": "m3",
    "M³": "m3",
    "RESMA": "Resma",
    "FDA": "Funda",
    "FUNDA": "Funda",
    "GL": "Galon",
    "GALON": "Galon",
    "GALÓN": "Galon",
    "CUBETA": "Cubeta",
    "CUB": "Cubeta",
    "ROLLO": "Rollo",
    "PA": "Units",
    "KIT": "Units",
    "PIE": "Pie",
    "DIAS": "Days",
    "DÍA": "Days",
    "DIA": "Days",
    "LB": "lb",
    "LBS": "lb",
}


def canon_uom(raw: str) -> str:
    key = strip_accents(collapse_ws(raw)).upper().replace(".", "")
    return UOM_MAP.get(key, "Units")


def is_service_description(desc: str) -> bool:
    d = norm_name(desc)
    service_markers = (
        "SERVICIO",
        "TRANSPORTE",
        "CORTE",
        "CARGA",
        "BOTE ",
        "GESTION",
        "DIRECCION TECNICA",
        "PEAJE",
        "COMBUSTIBLE",
        "CAJA CHICA",
        "TRASLADO",
        "REGADO",
        "PREPARACION",
        "RAMPA",
        "DT ",
    )
    return any(m in d for m in service_markers)


QA_NAME_RE = re.compile(r"\b(DXQA|DX TEST|DX-QA|TEST|QA)\b", re.I)
