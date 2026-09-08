"""Classify catalog sale-price quality. Never writes to Odoo."""

from __future__ import annotations

from .textutil import collapse

KEEP_ZERO = {
    "servicios profesionales",
    "servicio profesional",
}

LOW_RATIO = 0.30
HIGH_RATIO = 3.0
DIFF_RATIO = 0.20


def _pct(master: float, ref: float | None) -> float | None:
    if ref in (None, 0, 0.0):
        return None
    return round(((master - ref) / abs(ref)) * 100.0, 2)


def classify_price(row: dict) -> dict:
    name = row.get("name") or ""
    master = float(row.get("list_price") or 0)
    recent = row.get("recent_avg_price")
    last_q = row.get("last_quotation_price")
    last_s = row.get("last_sale_order_price")
    last_i = row.get("last_invoice_price")
    has_hist = any(v not in (None, "") for v in (last_q, last_s, last_i))
    pl_items = row.get("pricelist_items") or []
    notes = []
    status = "PRICE_OK"
    action = "KEEP"

    if pl_items:
        status = "PRICE_LIST_DEPENDENT"
        action = "PRICELIST_REVIEW"
        notes.append(f"pricelist_items={len(pl_items)}")
    elif abs(master) < 0.005:
        status = "ZERO_PRICE"
        if collapse(name) in KEEP_ZERO:
            action = "KEEP"
            notes.append("intentional zero for Servicios profesionales")
        else:
            action = "ZERO_PRICE_REVIEW"
            notes.append("list_price=0")
    elif has_hist and recent not in (None, 0, 0.0):
        ratio = master / abs(recent)
        diff = abs(master - recent) / abs(recent)
        if ratio < LOW_RATIO:
            status = "SUSPICIOUS_LOW"
            action = "REVIEW"
            notes.append(f"master={master} recent_avg={recent} ratio={ratio:.2f}")
        elif ratio > HIGH_RATIO:
            status = "SUSPICIOUS_HIGH"
            action = "REVIEW"
            notes.append(f"master={master} recent_avg={recent} ratio={ratio:.2f}")
        elif diff > DIFF_RATIO:
            status = "HISTORICAL_PRICE_DIFFERENCE"
            action = "UPDATE_CANDIDATE"
            notes.append(f"master={master} recent_avg={recent} diff_pct={diff*100:.1f}")
        else:
            status = "PRICE_OK"
            action = "KEEP"
            notes.append("master aligned with recent commercial prices")
    elif has_hist:
        status = "MANUAL_REVIEW"
        action = "REVIEW"
        notes.append("history exists but recent_avg is empty/zero")
    elif master > 0:
        status = "NO_SALES_HISTORY"
        action = "NO_ACTION"
        notes.append("has master price, no quotation/sale/invoice lines")
    else:
        status = "MANUAL_REVIEW"
        action = "REVIEW"
        notes.append("unclassified")

    ref = recent if recent not in (None, "") else last_i or last_s or last_q
    return {
        "price_status": status,
        "recommended_action": action,
        "price_difference_pct": _pct(master, ref),
        "notes": "; ".join(notes),
        "evidence": _evidence(row),
    }


def _evidence(row: dict) -> str:
    bits = []
    if row.get("last_quotation_price") is not None:
        bits.append(
            f"quote={row['last_quotation_price']}@{row.get('last_quotation_date') or ''}"
        )
    if row.get("last_sale_order_price") is not None:
        bits.append(
            f"so={row['last_sale_order_price']}@{row.get('last_sale_order_date') or ''}"
        )
    if row.get("last_invoice_price") is not None:
        bits.append(
            f"inv={row['last_invoice_price']}@{row.get('last_invoice_date') or ''}"
        )
    bits.append(f"master={row.get('list_price')}")
    return "; ".join(bits)
