"""Identidades de Formato Propet. Solo valores ya calculados por Odoo."""


def _line_qty(line):
    for fname in ("product_uom_qty", "quantity"):
        if hasattr(line, fname):
            try:
                return float(getattr(line, fname) or 0.0)
            except (TypeError, ValueError):
                continue
    return 0.0


def propet_line_amounts(line):
    """Lee importes fiscales de la línea. No recalcula ITBIS."""
    qty = _line_qty(line)
    unit_excl = float(getattr(line, "price_reduce_taxexcl", None) or 0.0)
    unit_incl = float(getattr(line, "price_reduce_taxinc", None) or 0.0)
    tax = float(getattr(line, "price_tax", None) or 0.0)
    subtotal = float(line.price_subtotal or 0.0)
    total = float(line.price_total or 0.0)
    if not tax and total and subtotal:
        tax = float(total) - float(subtotal)
    if qty and not unit_excl and subtotal:
        unit_excl = float(subtotal) / qty
    if qty and not unit_incl and total:
        unit_incl = float(total) / qty
    return {
        "qty": qty,
        "unit_excl": unit_excl,
        "unit_incl": unit_incl,
        "tax": tax,
        "subtotal": subtotal,
        "total": total,
        "discount": float(getattr(line, "discount", None) or 0.0),
    }


def propet_display_texts(product_name, display_name, line_name):
    """Split short product vs commercial description without repeating the name."""
    product_label = (product_name or display_name or "").strip()
    raw = (line_name or "").replace("\r\n", "\n").strip()
    if not raw:
        return product_label, ""
    needles = []
    for token in (display_name, product_name, product_label):
        token = (token or "").strip()
        if token and token not in needles:
            needles.append(token)
    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    while parts:
        dropped = False
        for token in needles:
            if parts[0] == token:
                parts.pop(0)
                dropped = True
                break
            if parts[0].startswith(token + " "):
                rest = parts[0][len(token) :].strip()
                if rest == token:
                    parts.pop(0)
                else:
                    parts[0] = rest
                dropped = True
                break
        if not dropped:
            break
    if parts and product_label and parts[0] == product_label:
        parts = parts[1:]
    return product_label, "\n".join(parts)


def propet_identities_ok(amounts, currency_rounding=0.01):
    """subtotal + ITBIS ≈ total; unitario * qty ≈ subtotal (tras descuento)."""
    tax_sum = abs((amounts["subtotal"] + amounts["tax"]) - amounts["total"])
    qty_sum = abs((amounts["unit_excl"] * amounts["qty"]) - amounts["subtotal"])
    return tax_sum <= currency_rounding + 1e-6 and qty_sum <= currency_rounding + 1e-6
