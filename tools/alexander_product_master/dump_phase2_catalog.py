# ruff: noqa
"""Read-only dump: products, decimal precision, sample list_price excess."""

import json

Precision = env["decimal.precision"].sudo()
Template = (
    env["product.template"]
    .sudo()
    .with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
)
rows = []
excess = []
for t in Template.search(
    [("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")]
):
    price = float(t.list_price or 0)
    cents = round(price * 100)
    # excess if not equal to 2-decimal monetary value
    rounded = round(price + 1e-12, 2)
    as_str = f"{price:.10f}".rstrip("0")
    decimals = 0
    if "." in as_str:
        decimals = len(as_str.split(".", 1)[1])
    rec = {
        "id": t.id,
        "product_variant_id": t.product_variant_id.id,
        "name": t.name or "",
        "type": t.type,
        "list_price": price,
        "list_price_repr": repr(price),
        "standard_price": float(t.standard_price or 0),
        "sale_ok": bool(t.sale_ok),
        "purchase_ok": bool(t.purchase_ok),
        "uom": t.uom_id.name if t.uom_id else "",
        "categ": t.categ_id.name if t.categ_id else "",
        "company_id": t.company_id.id or False,
        "company_name": t.company_id.name if t.company_id else "",
        "default_code": t.default_code or "",
        "barcode": t.barcode or "",
        "decimals_visible": decimals,
    }
    rows.append(rec)
    if abs(price - rounded) > 1e-9 or decimals > 2:
        excess.append(rec)

print(
    json.dumps(
        {
            "count": len(rows),
            "decimal_precision": [
                {"name": p.name, "digits": int(p.digits)} for p in Precision.search([])
            ],
            "currency_decimals": [
                {"name": c.name, "decimal_places": int(c.decimal_places)}
                for c in env["res.currency"].sudo().search([("active", "=", True)])
            ],
            "excess_count": len(excess),
            "excess_sample": excess[:40],
            "products": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
)
