from __future__ import annotations

TOL = 0.05  # relative, plus 0.05 absolute for small numbers


def _close(a, b) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(0.05, abs(b) * TOL)


def unit_price_excl_tax(row: dict) -> tuple[float | None, str]:
    """Return (price_excl_tax, status). Never uses cost-analysis as sales price."""
    if row.get("document_type") == "COST_ANALYSIS":
        return None, "COST_NOT_SALE_PRICE"
    qty = row.get("quantity") or 1.0
    raw = row.get("raw_unit_price")
    excl = row.get("price_excl_hint")
    itbis = row.get("itbis")
    subtotal = row.get("subtotal")
    total = row.get("total")

    if excl and excl > 0:
        if (
            qty
            and subtotal
            and not _close(excl * qty, subtotal)
            and _close(excl, subtotal)
        ):
            return None, "PRICE_COLUMN_AMBIGUOUS"
        return round(excl, 4), "EXCL_HINT"

    if raw is None or raw <= 0:
        if subtotal and qty and qty > 0:
            unit = subtotal / qty
            if unit > 0:
                return round(unit, 4), "FROM_SUBTOTAL"
        return None, "MISSING_VALID_PRICE"

    # If raw * qty ~= subtotal → raw is excl
    if qty and subtotal and _close(raw * qty, subtotal):
        return round(raw, 4), "RECONCILED_SUBTOTAL"
    # If raw * qty * 1.18 ~= total → raw is excl
    if qty and total and _close(raw * qty * 1.18, total):
        return round(raw, 4), "RECONCILED_TOTAL_TAX"
    # If raw * qty ~= total and itbis is 0/None → raw is excl
    if qty and total and _close(raw * qty, total) and not itbis:
        return round(raw, 4), "RECONCILED_TOTAL_NO_TAX"
    # If raw looks like line total
    if qty and qty > 1 and subtotal and _close(raw, subtotal):
        return None, "PRICE_COLUMN_AMBIGUOUS"
    if qty and qty > 1 and total and _close(raw, total):
        return None, "PRICE_COLUMN_AMBIGUOUS"
    # If itbis present and raw*0.18 ~= itbis / qty
    if itbis and qty and _close(raw * 0.18 * qty, itbis):
        return round(raw, 4), "RECONCILED_ITBIS"
    if itbis and qty and _close((raw / 1.18) * 0.18 * qty, itbis):
        return round(raw / 1.18, 4), "RECONCILED_ITBIS_INCL"
    # Single unit, no math: keep as excl only for quotations/invoices/lists
    if (
        row.get("document_type") in {"QUOTATION", "INVOICE", "PRODUCT_LIST"}
        and (qty or 0) <= 1
    ):
        return round(raw, 4), "ASSUMED_EXCL_QTY1"
    if row.get("document_type") in {"QUOTATION", "INVOICE"}:
        return round(raw, 4), "ASSUMED_EXCL"
    return None, "PRICE_COLUMN_AMBIGUOUS"


def pick_max_price(values: list[float]) -> tuple[float | None, str]:
    clean = sorted(v for v in values if v and v > 0)
    if not clean:
        return None, "NO_PRICE"
    if len(clean) == 1:
        return clean[0], "SINGLE"
    hi, rest = clean[-1], clean[:-1]
    median = rest[len(rest) // 2]
    if median > 0 and hi / median >= 8:
        return None, "PRICE_OUTLIER_REVIEW"
    return hi, "MAX"
