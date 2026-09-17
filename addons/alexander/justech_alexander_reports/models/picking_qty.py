"""Ordered vs delivered quantities for Conduce. Presentation only."""


def picking_line_qtys(move):
    """Cantidad pedida from the sale line; delivered from the picking move."""
    ordered = 0.0
    sale_line = getattr(move, "sale_line_id", False)
    if sale_line is not False and sale_line:
        try:
            ordered = float(getattr(sale_line, "product_uom_qty", 0.0) or 0.0)
        except (TypeError, ValueError):
            ordered = 0.0
    if not ordered:
        try:
            ordered = float(getattr(move, "product_uom_qty", 0.0) or 0.0)
        except (TypeError, ValueError):
            ordered = 0.0
    done = 0.0
    for fname in ("quantity", "quantity_done"):
        if hasattr(move, fname):
            try:
                done = float(getattr(move, fname) or 0.0)
                break
            except (TypeError, ValueError):
                continue
    return ordered, done
