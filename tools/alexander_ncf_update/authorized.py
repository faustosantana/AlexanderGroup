"""Authorized B15 source data for 2026-09-26. No secrets."""

from __future__ import annotations

from datetime import date

# Resolve live records by short code / name, never by staging IDs.
AUTHORIZED_B15 = {
    "DOR": {
        "key": "DORALEX",
        "needles": ("INVERSIONES DORALEX",),
        "prefix": "B15",
        "sequence_start": 141,
        "sequence_end": 160,
        "last_used": 151,
        "next_sequence": 152,
        "date_to": date(2027, 12, 31),
        "authorization_number": "6005109381",
        "ncf_from": "B1500000141",
        "ncf_to": "B1500000160",
        "ncf_last": "B1500000151",
        "ncf_next": "B1500000152",
    },
    "MAY": {
        "key": "MAYUMA",
        "needles": ("EL MAYUMA",),
        "prefix": "B15",
        "sequence_start": 109,
        "sequence_end": 118,
        "last_used": 112,
        "next_sequence": 113,
        "date_to": date(2026, 12, 31),
        "authorization_number": "5004942280",
        "ncf_from": "B1500000109",
        "ncf_to": "B1500000118",
        "ncf_last": "B1500000112",
        "ncf_next": "B1500000113",
    },
    "REM": {
        "key": "REMPART",
        "needles": ("REMPART GROUP",),
        "prefix": "B15",
        "sequence_start": 106,
        "sequence_end": 113,
        "last_used": 111,
        "next_sequence": 112,
        "date_to": date(2027, 1, 3),
        "authorization_number": "5004942351",
        "ncf_from": "B1500000106",
        "ncf_to": "B1500000113",
        "ncf_last": "B1500000111",
        "ncf_next": "B1500000112",
    },
}

QA_MIN = 99100000
QA_NAME_MARKERS = ("DX TEST", "DXQA", "NO FISCAL", "NO ENVIAR DGII")
WARNING_REMAINING = 10
CRITICAL_REMAINING = 3
EXPIRY_ALERT_DAYS = 30


def format_ncf(prefix: str, number: int) -> str:
    return f"{prefix}{int(number):08d}"


def remaining(end: int, last_used: int) -> int:
    return max(int(end) - int(last_used), 0)


def parse_b15(ncf: str) -> int | None:
    text = (ncf or "").strip().upper()
    if len(text) < 11 or not text.startswith("B15"):
        return None
    digits = text[3:]
    if not digits.isdigit():
        return None
    value = int(digits)
    if value >= QA_MIN:
        return None
    return value
