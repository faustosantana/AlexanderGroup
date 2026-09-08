# ruff: noqa
"""Read-only: product.template type fields and catalog type distribution."""

import json

Template = env["product.template"]
fields = Template.fields_get(
    [
        "type",
        "is_storable",
        "is_favorite",
        "sale_ok",
        "purchase_ok",
        "invoice_policy",
        "service_tracking",
        "service_type",
        "tracking",
        "valuation",
        "cost_method",
        "categ_id",
        "company_id",
        "uom_id",
        "uom_po_id",
        "list_price",
        "standard_price",
        "active",
    ]
)
field_report = {}
for name, meta in fields.items():
    field_report[name] = {
        "type": meta.get("type"),
        "string": meta.get("string"),
        "selection": meta.get("selection"),
        "readonly": meta.get("readonly"),
        "store": meta.get("store"),
        "related": meta.get("related"),
        "depends": meta.get("depends"),
        "help": (meta.get("help") or "")[:240],
    }

all_names = sorted(Template.fields_get().keys())
type_like = [n for n in all_names if any(k in n for k in ("type", "stor", "stock", "track", "valu"))]

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
T = Template.sudo().with_context(**ctx)
recs = T.search([("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")])
dist = {}
storable = {"true": 0, "false": 0, "missing": 0}
purchase_false = 0
service_ids = []
for t in recs:
    dist[t.type] = dist.get(t.type, 0) + 1
    if "is_storable" in t._fields:
        if t.is_storable:
            storable["true"] += 1
        else:
            storable["false"] += 1
    else:
        storable["missing"] += 1
    if not t.purchase_ok:
        purchase_false += 1
    if t.type == "service":
        service_ids.append(
            {
                "id": t.id,
                "name": t.name,
                "purchase_ok": bool(t.purchase_ok),
                "sale_ok": bool(t.sale_ok),
                "active": bool(t.active),
                "company": t.company_id.name if t.company_id else "",
                "categ": t.categ_id.name if t.categ_id else "",
                "list_price": float(t.list_price or 0),
            }
        )

focus = {}
for pid in (21, 138, 168, 321):
    rec = T.browse(pid)
    if rec.exists():
        focus[pid] = {
            "name": rec.name,
            "type": rec.type,
            "is_storable": bool(rec.is_storable) if "is_storable" in rec._fields else None,
            "sale_ok": bool(rec.sale_ok),
            "purchase_ok": bool(rec.purchase_ok),
            "active": bool(rec.active),
            "company_id": rec.company_id.id or False,
            "standard_price": float(rec.standard_price or 0),
        }

pinaria = T.search(
    [("company_id.name", "ilike", "pinaria")]
) | T.search([("company_id.name", "ilike", "piñaria")])
pinaria_rows = [
    {
        "id": t.id,
        "name": t.name,
        "type": t.type,
        "company": t.company_id.name if t.company_id else "",
        "purchase_ok": bool(t.purchase_ok),
        "active": bool(t.active),
    }
    for t in pinaria
]

print(
    json.dumps(
        {
            "PRODUCT_TYPE_FIELDS": field_report,
            "TYPE_LIKE_FIELDS": type_like,
            "PRODUCTS_SCANNED": len(recs),
            "TYPE_DISTRIBUTION": dist,
            "IS_STORABLE_DISTRIBUTION": storable,
            "PURCHASE_OK_FALSE": purchase_false,
            "SERVICE_COUNT": len(service_ids),
            "SERVICE_PRODUCTS": service_ids,
            "FOCUS": focus,
            "PINARIA": pinaria_rows,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
