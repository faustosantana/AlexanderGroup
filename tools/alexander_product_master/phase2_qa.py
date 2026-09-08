# ruff: noqa
"""Phase 2 QA: 2-decimal list_price, pinaria isolation, no stock/docs changes."""

import json
from decimal import ROUND_HALF_UP, Decimal


def money2(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


Template = (
    env["product.template"]
    .sudo()
    .with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
)
products = Template.search(
    [("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")]
)
excess = []
for t in products:
    price = float(t.list_price or 0)
    if Decimal(str(price)) != money2(price):
        excess.append({"id": t.id, "name": t.name, "list_price": price})

pinaria = next(
    (
        c
        for c in env["res.company"].sudo().search([])
        if "pinaria" in (c.name or "").lower().replace("ñ", "n")
    ),
    None,
)
pinaria_prods = products.filtered(lambda t: pinaria and t.company_id == pinaria)
shared = products.filtered(lambda t: not t.company_id)
svc = products.filtered(
    lambda t: (t.name or "").strip().lower() == "servicios profesionales"
)
posted = (
    env["account.move"]
    .sudo()
    .search_count([("move_type", "=", "out_invoice"), ("state", "=", "posted")])
)
recent_moves = 0
if "stock.move" in env:
    recent_moves = (
        env["stock.move"]
        .sudo()
        .search_count([("create_date", ">=", "2026-09-08 00:00:00")])
    )

# Product Price digits
prec = env["decimal.precision"].sudo().search([("name", "=", "Product Price")], limit=1)

report = {
    "PRODUCT_COUNT": len(products),
    "SHARED_PRODUCTS": len(shared),
    "PINARIA_ONLY_PRODUCTS": len(pinaria_prods),
    "PINARIA_SAMPLE": [
        {
            "id": t.id,
            "name": t.name,
            "company": t.company_id.name,
            "list_price": float(t.list_price),
            "sale_ok": t.sale_ok,
            "purchase_ok": t.purchase_ok,
        }
        for t in pinaria_prods
    ],
    "SERVICIOS_PROFESIONALES_ID": svc[0].id if svc else None,
    "SERVICIOS_PROFESIONALES_LIST_PRICE": float(svc[0].list_price) if svc else None,
    "ODOO_PRODUCT_PRICE_DIGITS": int(prec.digits) if prec else None,
    "PRODUCT_PRICES_STILL_ABOVE_2_DECIMALS": len(excess),
    "EXCESS_SAMPLE": excess[:15],
    "POSTED_INVOICES": posted,
    "STOCK_MOVES_CREATED_TODAY": recent_moves,
    "CRITICAL_ERRORS": 0,
    "HIGH_ERRORS": 0,
}
if report["PRODUCT_PRICES_STILL_ABOVE_2_DECIMALS"]:
    report["HIGH_ERRORS"] += 1
if report["SERVICIOS_PROFESIONALES_LIST_PRICE"] not in (0, 0.0):
    report["HIGH_ERRORS"] += 1
if report["POSTED_INVOICES"] != 27:
    report["CRITICAL_ERRORS"] += 1
if report["ODOO_PRODUCT_PRICE_DIGITS"] != 2:
    report["HIGH_ERRORS"] += 1
report["PHASE2_QA"] = (
    "PASS" if not report["CRITICAL_ERRORS"] and not report["HIGH_ERRORS"] else "FAIL"
)
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
