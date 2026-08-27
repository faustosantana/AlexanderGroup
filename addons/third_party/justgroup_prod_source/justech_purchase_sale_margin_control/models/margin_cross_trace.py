# -*- coding: utf-8 -*-
"""Cross-module traceability helpers — single source: purchase.sale.margin.transaction.

No duplicate relations. Documents only read M2M hubs on the margin operation.
"""
from odoo import _


def float_is_zero_safe(value, digits=2):
    try:
        from odoo.tools.float_utils import float_is_zero

        return float_is_zero(value or 0.0, precision_digits=digits)
    except Exception:  # noqa: BLE001
        return abs(value or 0.0) < 10 ** (-digits)


def active_purchase_orders(pos):
    """UX/cost surfaces: cancelled POs stay in MTX audit M2M but must not appear active."""
    if not pos:
        return pos
    return pos.filtered(lambda p: p.state != "cancel")


def active_vendor_bills(moves):
    """UX surfaces: cancelled / zero-qty phantom bills must not appear as related cost docs."""
    if not moves:
        return moves
    return moves.filtered(
        lambda m: m.state != "cancel"
        and m.move_type in ("in_invoice", "in_refund")
        and (
            not float_is_zero_safe(m.amount_untaxed)
            or any(
                (l.quantity or 0.0) > 0
                for l in m.invoice_line_ids
                if not getattr(l, "display_type", False)
            )
        )
    )


def join_record_names(records, field="display_name", empty="—"):
    """Join record labels safely (draft account.move.name can be False)."""
    names = []
    for rec in records:
        label = rec[field] if field in rec._fields else False
        if not label and field != "display_name" and "display_name" in rec._fields:
            label = rec.display_name
        if label:
            names.append(str(label))
    return ", ".join(names) if names else empty


def margin_band_label(band):
    mapping = {
        "positive": "SALUDABLE",
        "healthy": "SALUDABLE",
        "low": "BAJO",
        "negative": "NEGATIVO",
        "pending": "PENDIENTE",
    }
    key = band or "pending"
    # Prefer gettext when a language is available; fall back to Spanish literals in tests/CLI.
    try:
        return _(mapping.get(key, key))
    except Exception:  # noqa: BLE001
        return mapping.get(key, key or "PENDIENTE")


def cost_origin_label(txs):
    """Infer cost origin labels from linked docs / inventory flags."""
    labels = []
    if not txs:
        return _("—")
    if any(t.purchase_order_ids or t.vendor_bill_ids for t in txs):
        labels.append(_("compra directa"))
    for t in txs:
        if getattr(t, "has_inventory_cost", False):
            labels.append(_("inventario"))
            break
    if any((t.additional_cost_amount or 0.0) for t in txs):
        labels.append(_("adicional"))
    else:
        Alloc = txs.env["purchase.sale.cost.allocation"]
        sale_ids = txs.mapped("sale_order_ids").ids
        if sale_ids and Alloc.search_count(
            [
                ("sale_order_id", "in", sale_ids),
                ("cost_usage_type", "in", ("logistic", "financial", "other")),
            ]
        ):
            labels.append(_("adicional"))
    if any((t.source or "") == "manual" for t in txs):
        labels.append(_("manual"))
    seen = []
    for lbl in labels:
        if lbl not in seen:
            seen.append(lbl)
    return ", ".join(seen) if seen else _("—")
