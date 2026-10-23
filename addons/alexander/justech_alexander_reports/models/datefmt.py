"""Printed Doralex dates are always day/month/year, independent of lang."""

from datetime import date, datetime

DX_DATE_FMT = "%d/%m/%Y"


def dx_format_date(value):
    if value in (None, False, ""):
        return "—"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "—"
        try:
            value = date.fromisoformat(text[:10])
        except ValueError:
            return text
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime(DX_DATE_FMT)
    if hasattr(value, "strftime"):
        return value.strftime(DX_DATE_FMT)
    return "—"
