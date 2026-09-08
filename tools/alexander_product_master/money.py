"""Deterministic commercial rounding for catalog sale prices."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TWOPLACES = Decimal("0.01")


def money2(value) -> Decimal:
    """Round a sale price to 2 decimals with half-up (not floor/truncate)."""
    if value in (None, ""):
        raise ValueError("empty price")
    if isinstance(value, Decimal):
        raw = value
    else:
        raw = Decimal(str(value))
    return raw.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def money2_float(value) -> float:
    return float(money2(value))


def has_excess_precision(value) -> bool:
    if value in (None, ""):
        return False
    raw = Decimal(str(value))
    return raw != money2(raw)
