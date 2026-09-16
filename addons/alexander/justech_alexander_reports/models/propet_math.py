"""Identidades de Formulario Propet. Solo valores ya calculados por Odoo."""


def propet_line_amounts(line):
    """Lee importes fiscales de la línea. No recalcula ITBIS."""
    qty = float(line.product_uom_qty or 0.0)
    unit_excl = float(getattr(line, "price_reduce_taxexcl", None) or 0.0)
    unit_incl = float(getattr(line, "price_reduce_taxinc", None) or 0.0)
    tax = float(getattr(line, "price_tax", None) or 0.0)
    subtotal = float(line.price_subtotal or 0.0)
    total = float(line.price_total or 0.0)
    return {
        "qty": qty,
        "unit_excl": unit_excl,
        "unit_incl": unit_incl,
        "tax": tax,
        "subtotal": subtotal,
        "total": total,
    }


def propet_identities_ok(amounts, currency_rounding=0.01):
    """subtotal + ITBIS ≈ total; unitario * qty ≈ subtotal (tras descuento)."""
    tax_sum = abs((amounts["subtotal"] + amounts["tax"]) - amounts["total"])
    qty_sum = abs((amounts["unit_excl"] * amounts["qty"]) - amounts["subtotal"])
    return tax_sum <= currency_rounding + 1e-6 and qty_sum <= currency_rounding + 1e-6
