# ruff: noqa
"""Read-only / SAVEPOINT QA after product master import. No invoices, no mail, no stock."""

import json
import unicodedata
import re

BATCH = "ALEXANDER_PRODUCT_MASTER_20260907"


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


Template = (
    env["product.template"]
    .sudo()
    .with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
)
Company = env["res.company"].sudo()
companies = {c.id: c.name for c in Company.search([])}
pinaria = next(
    (c for c in Company.search([]) if "pinaria" in _fold(c.name).replace("ñ", "n")),
    None,
)

templates = Template.search(
    [("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")]
)
by_norm = {}
dups = []
for t in templates:
    key = _fold(t.name)
    by_norm.setdefault(key, []).append(t.id)
for key, ids in by_norm.items():
    if len(ids) > 1:
        dups.append({"name": key, "ids": ids})

svc = templates.filtered(lambda t: _fold(t.name) == "servicios profesionales")
admin_hits = templates.filtered(
    lambda t: _fold(t.name)
    in {"subtotal", "total", "itbis", "descuento", "gastos administrativos"}
    or _fold(t.name).startswith("itbis")
    or _fold(t.name).startswith("sub total")
)

food = templates.filtered(
    lambda t: t.categ_id.name in {"Alimentos", "Carnes"} or t.company_id == pinaria
)
shared = templates.filtered(lambda t: not t.company_id)

stock_moves = (
    env["stock.move"].sudo().search_count([("create_uid", "=", env.uid)])
    if "stock.move" in env
    else 0
)

# posted invoice count must stay 27
posted = (
    env["account.move"]
    .sudo()
    .search_count([("move_type", "=", "out_invoice"), ("state", "=", "posted")])
)

# sample shared product visibility: company_id False
sample_shared = templates.filtered(
    lambda t: any(
        x in _fold(t.name)
        for x in ("cemento", "taladro", "pintura", "televisor", "nevera")
    )
    and not t.company_id
)[:8]

food_leak = [
    {"id": t.id, "name": t.name, "company": t.company_id.name or "SHARED"}
    for t in food
    if t.company_id and pinaria and t.company_id != pinaria
]
food_shared_wrong = [
    {"id": t.id, "name": t.name}
    for t in templates
    if t.categ_id.name in {"Alimentos", "Carnes"} and not t.company_id
]

report = {
    "BATCH": BATCH,
    "PRODUCT_COUNT": len(templates),
    "SHARED_PRODUCTS": len(shared),
    "PINARIA_SCOPED": len(
        templates.filtered(lambda t: pinaria and t.company_id == pinaria)
    ),
    "SERVICIOS_PROFESIONALES_COUNT": len(svc),
    "SERVICIOS_PROFESIONALES_ID": svc[0].id if svc else None,
    "SERVICIOS_PROFESIONALES_LIST_PRICE": float(svc[0].list_price) if svc else None,
    "FALSE_PRODUCT_TOTAL_ROWS": len(admin_hits),
    "FALSE_PRODUCT_NAMES": [t.name for t in admin_hits[:20]],
    "NORMALIZED_NAME_DUPLICATES": len(dups),
    "DUPLICATE_SAMPLES": dups[:15],
    "FOOD_WRONG_COMPANY": food_leak,
    "FOOD_SHARED_WRONG": food_shared_wrong[:20],
    "POSTED_INVOICES": posted,
    "STOCK_MOVES_THIS_UID": stock_moves,
    "SAMPLE_SHARED": [
        {
            "id": t.id,
            "name": t.name,
            "company_id": t.company_id.id or False,
            "list_price": float(t.list_price),
        }
        for t in sample_shared
    ],
    "CRITICAL_ERRORS": 0,
    "HIGH_ERRORS": 0,
}

if report["SERVICIOS_PROFESIONALES_COUNT"] != 1:
    report["HIGH_ERRORS"] += 1
if report["SERVICIOS_PROFESIONALES_LIST_PRICE"] not in (0, 0.0):
    report["HIGH_ERRORS"] += 1
if report["FALSE_PRODUCT_TOTAL_ROWS"]:
    report["HIGH_ERRORS"] += 1
if report["POSTED_INVOICES"] != 27:
    report["CRITICAL_ERRORS"] += 1
if food_leak:
    report["HIGH_ERRORS"] += 1
if report["CRITICAL_ERRORS"] or report["HIGH_ERRORS"]:
    report["STAGING_PRODUCT_QA"] = "FAIL"
else:
    report["STAGING_PRODUCT_QA"] = "PASS"

print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
