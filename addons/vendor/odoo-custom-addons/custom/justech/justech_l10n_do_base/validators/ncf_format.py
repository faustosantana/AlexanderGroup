"""Validación pura de formato NCF (11 caracteres)."""
from __future__ import annotations

import re

NCF_FULL_RE = re.compile(r"^[BE][0-9]{2}[0-9]{8}$")


def normalize_ncf(ncf: str | None) -> str:
    return (ncf or "").strip().upper().replace(" ", "")


def validate_ncf_format(ncf: str | None) -> str:
    """Devuelve NCF normalizado o lanza ValueError."""
    normalized = normalize_ncf(ncf)
    if not NCF_FULL_RE.match(normalized):
        raise ValueError(
            "Invalid NCF format. Expected 11 characters (e.g. B0100000001)."
        )
    return normalized


def parse_ncf(ncf: str | None) -> tuple[str | bool, int | bool]:
    """Parsea NCF en (prefijo 3 chars, secuencia int) o (False, False)."""
    normalized = normalize_ncf(ncf)
    if len(normalized) != 11:
        return False, False
    return normalized[:3], int(normalized[3:])
