# ruff: noqa
"""Read-only dump of the full catalog + reference counts + type fields.

Writes JSON to PRODUCT_TYPE_DUMP (default /tmp/product_type_dump.json).
Does not create products, stock, or documents.
"""

import json
import os
from collections import defaultdict

OUT = os.environ.get("PRODUCT_TYPE_DUMP", "/tmp/product_type_dump.json")

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
Template = env["product.template"].sudo().with_context(**ctx)
Product = env["product.product"].sudo().with_context(**ctx)

fields_meta = Template.fields_get(["type", "is_storable", "sale_ok", "purchase_ok"])
type_selection = fields_meta.get("type", {}).get("selection") or []

recs = Template.search(
    [("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")]
)
variant_to_tmpl = {}
products = []
for t in recs:
    variant = t.product_variant_id
    vid = variant.id if variant else None
    if vid:
        variant_to_tmpl[vid] = t.id
    products.append(
        {
            "PRODUCT_ID": vid,
            "TEMPLATE_ID": t.id,
            "NAME": t.name or "",
            "TYPE": t.type,
            "IS_STORABLE": bool(t.is_storable) if "is_storable" in t._fields else None,
            "SALE_OK": bool(t.sale_ok),
            "PURCHASE_OK": bool(t.purchase_ok),
            "UOM": t.uom_id.name if t.uom_id else "",
            "CATEGORY": t.categ_id.name if t.categ_id else "",
            "COMPANY_ID": t.company_id.id or False,
            "COMPANY": t.company_id.name if t.company_id else "",
            "LIST_PRICE": float(t.list_price or 0),
            "STANDARD_PRICE": float(t.standard_price or 0),
            "ACTIVE": bool(t.active),
            "CREATE_DATE": str(t.create_date),
        }
    )

ref_models = [
    ("SALE_LINE_REFERENCES", "sale.order.line", "product_id"),
    ("PURCHASE_LINE_REFERENCES", "purchase.order.line", "product_id"),
    ("INVOICE_LINE_REFERENCES", "account.move.line", "product_id"),
    ("STOCK_MOVE_REFERENCES", "stock.move", "product_id"),
    ("STOCK_MOVE_LINE_REFERENCES", "stock.move.line", "product_id"),
    ("STOCK_QUANT_REFERENCES", "stock.quant", "product_id"),
]
counts = {key: defaultdict(int) for key, *_ in ref_models}
for key, model, field in ref_models:
    if model not in env:
        continue
    groups = env[model].sudo().read_group(
        [(field, "!=", False)], [field], [field]
    )
    for g in groups:
        pid = g.get(field)[0] if g.get(field) else None
        if pid:
            counts[key][pid] = int(g.get(f"{field}_count") or g.get("__count") or 0)

valuation_counts = defaultdict(int)
if "stock.valuation.layer" in env:
    for g in env["stock.valuation.layer"].sudo().read_group(
        [("product_id", "!=", False)], ["product_id"], ["product_id"]
    ):
        pid = g.get("product_id")[0] if g.get("product_id") else None
        if pid:
            valuation_counts[pid] = int(
                g.get("product_id_count") or g.get("__count") or 0
            )

for row in products:
    pid = row["PRODUCT_ID"]
    for key, *_ in ref_models:
        row[key] = counts[key].get(pid, 0)
    row["VALUATION_LAYER_REFERENCES"] = valuation_counts.get(pid, 0)

ncf_changed_probe = 0
if "l10n_latam.document.number" in env["account.move"]._fields:
    ncf_changed_probe = env["account.move"].sudo().search_count(
        [("move_type", "in", ["out_invoice", "in_invoice"]), ("state", "=", "posted")]
    )

storable = [p for p in products if p["IS_STORABLE"]]
services = [p for p in products if p["TYPE"] == "service"]
purchase_false = [p for p in products if not p["PURCHASE_OK"]]
sale_false = [p for p in products if not p["SALE_OK"]]
pinaria = [
    p
    for p in products
    if "pinaria" in (p["COMPANY"] or "").lower().replace("ñ", "n")
]

payload = {
    "PRODUCT_TYPE_FIELDS": {
        "type": {
            "selection": type_selection,
            "string": fields_meta.get("type", {}).get("string"),
            "help": (fields_meta.get("type", {}).get("help") or "")[:240],
        },
        "is_storable": {
            "string": fields_meta.get("is_storable", {}).get("string"),
            "help": (fields_meta.get("is_storable", {}).get("help") or "")[:240],
            "present": "is_storable" in Template._fields,
        },
    },
    "CURRENT_GOODS_IMPLEMENTATION": "type='consu' (Goods), is_storable=False unless inventory is tracked",
    "CURRENT_SERVICE_IMPLEMENTATION": "type='service' (Service), is_storable is ignored/False",
    "PRODUCTS_AUDITED": len(products),
    "TYPE_DISTRIBUTION": {
        k: sum(1 for p in products if p["TYPE"] == k)
        for k in sorted({p["TYPE"] for p in products})
    },
    "IS_STORABLE_TRUE": storable,
    "SERVICE_PRODUCTS": services,
    "PURCHASE_OK_FALSE": [
        {"PRODUCT_ID": p["PRODUCT_ID"], "TEMPLATE_ID": p["TEMPLATE_ID"], "NAME": p["NAME"], "TYPE": p["TYPE"], "ACTIVE": p["ACTIVE"]}
        for p in purchase_false
    ],
    "SALE_OK_FALSE": [
        {"PRODUCT_ID": p["PRODUCT_ID"], "TEMPLATE_ID": p["TEMPLATE_ID"], "NAME": p["NAME"], "TYPE": p["TYPE"], "ACTIVE": p["ACTIVE"]}
        for p in sale_false
    ],
    "PINARIA_PRODUCTS": pinaria,
    "POSTED_INVOICES": env["account.move"]
    .sudo()
    .search_count([("move_type", "=", "out_invoice"), ("state", "=", "posted")]),
    "products": products,
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
print(
    json.dumps(
        {
            "wrote": OUT,
            "PRODUCTS_AUDITED": len(products),
            "TYPE_DISTRIBUTION": payload["TYPE_DISTRIBUTION"],
            "SERVICE_COUNT": len(services),
            "PURCHASE_OK_FALSE": len(purchase_false),
            "SALE_OK_FALSE": len(sale_false),
            "PINARIA": len(pinaria),
            "STORABLE_TRUE": len(storable),
        },
        ensure_ascii=False,
        indent=2,
    )
)
