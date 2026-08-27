"""Validación pura de RNC / cédula dominicana (sin dependencias Odoo)."""
from __future__ import annotations

import re

RNC_RE = re.compile(r"^\d{9,11}$")


def normalize_vat(vat: str | None) -> str:
    """Elimina espacios y guiones del identificador fiscal."""
    return re.sub(r"[\s\-]", "", (vat or ""))


def is_valid_rnc_format(vat: str | None) -> bool:
    """True si el formato cumple 9–11 dígitos numéricos."""
    cleaned = normalize_vat(vat)
    return bool(cleaned and RNC_RE.match(cleaned))


def dgii_id_type_from_vat(vat: str | None) -> str | None:
    """Código DGII: 1=RNC (9), 2=Cédula (11), None si no aplica."""
    cleaned = normalize_vat(vat)
    if len(cleaned) == 9:
        return "1"
    if len(cleaned) == 11:
        return "2"
    return None
