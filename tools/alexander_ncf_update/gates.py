"""Pure gates for the authorized B15 update. No Odoo, no sequence consume."""

from __future__ import annotations

from datetime import date, timedelta

try:
    from .authorized import (
        AUTHORIZED_B15,
        CRITICAL_REMAINING,
        EXPIRY_ALERT_DAYS,
        WARNING_REMAINING,
        format_ncf,
        remaining,
    )
except ImportError:  # copied to /tmp on the Odoo host
    from authorized import (
        AUTHORIZED_B15,
        CRITICAL_REMAINING,
        EXPIRY_ALERT_DAYS,
        WARNING_REMAINING,
        format_ncf,
        remaining,
    )


def gate_range(spec: dict) -> list[str]:
    errors = []
    start = spec["sequence_start"]
    end = spec["sequence_end"]
    nxt = spec["next_sequence"]
    last_used = spec["last_used"]
    if nxt != last_used + 1:
        errors.append("NEXT_NOT_LAST_PLUS_ONE")
    if nxt < start:
        errors.append("NEXT_BELOW_START")
    if nxt > end:
        errors.append("NEXT_ABOVE_END")
    if last_used < start - 1 or last_used > end:
        errors.append("LAST_USED_OUT_OF_RANGE")
    if format_ncf(spec["prefix"], start) != spec["ncf_from"]:
        errors.append("FROM_FORMAT")
    if format_ncf(spec["prefix"], end) != spec["ncf_to"]:
        errors.append("TO_FORMAT")
    if format_ncf(spec["prefix"], nxt) != spec["ncf_next"]:
        errors.append("NEXT_FORMAT")
    return errors


def gate_max_real(spec: dict, max_real: int | None) -> list[str]:
    """Hard-stop only when Odoo is ahead of the authorized last used."""
    if max_real is None:
        return ["MAX_REAL_MISSING"]
    if int(max_real) > int(spec["last_used"]):
        return ["MAX_REAL_AHEAD_OF_AUTHORIZATION"]
    return []


def paper_gap(spec: dict, max_real: int | None) -> bool:
    return max_real is not None and int(max_real) < int(spec["last_used"])


def gate_next_exists(spec: dict, next_exists: bool) -> list[str]:
    if next_exists:
        return ["NEXT_NCF_ALREADY_EXISTS"]
    return []


def classify_balance(remaining_count: int, date_to: date | None, today: date) -> str:
    if date_to and today > date_to:
        return "EXPIRED"
    left = int(remaining_count)
    if left <= 0:
        return "EXHAUSTED"
    if left <= CRITICAL_REMAINING:
        return "CRITICAL"
    if left <= WARNING_REMAINING:
        return "WARNING"
    if date_to and today <= date_to <= today + timedelta(days=EXPIRY_ALERT_DAYS):
        return "WARNING"
    return "NORMAL"


def expected_remaining(code: str) -> int:
    spec = AUTHORIZED_B15[code]
    return remaining(spec["sequence_end"], spec["last_used"])


def authorized_specs():
    return AUTHORIZED_B15
