# ruff: noqa
"""Read-only audit of the two Grava 3/4 product templates. No writes."""

import json

NEEDLES = (
    "(AGREGADO GRUESO) GRAVA 3/4",
    "AGREGADO GRUESO (GRAVA) 3/4",
)

Template = (
    env["product.template"]
    .sudo()
    .with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
)
Product = env["product.product"].sudo().with_context(active_test=False)

found = Template.search(
    [
        "|",
        ("name", "in", list(NEEDLES)),
        ("name", "ilike", "grava 3/4"),
    ]
)

REF_MODELS = [
    ("sale.order.line", "product_id"),
    ("purchase.order.line", "product_id"),
    ("account.move.line", "product_id"),
    ("stock.move", "product_id"),
    ("stock.move.line", "product_id"),
    ("stock.quant", "product_id"),
]


def _count(model, field, variant_ids):
    if model not in env:
        return {"exists": False, "count": 0, "posted": 0, "sample": []}
    Model = env[model].sudo()
    recs = Model.search([(field, "in", variant_ids)])
    posted = 0
    sample = []
    for rec in recs[:8]:
        row = {"id": rec.id}
        if "order_id" in rec._fields:
            row["order"] = rec.order_id.name
            row["state"] = rec.order_id.state
        if "move_id" in rec._fields:
            row["move"] = rec.move_id.name
            row["state"] = rec.move_id.state
            if rec.move_id.state == "posted":
                posted += 1
        if "state" in rec._fields and "state" not in row:
            row["state"] = rec.state
        sample.append(row)
    if model == "account.move.line":
        posted = Model.search_count(
            [(field, "in", variant_ids), ("move_id.state", "=", "posted")]
        )
    return {"exists": True, "count": len(recs), "posted": posted, "sample": sample}


rows = []
for t in found:
    variants = t.product_variant_ids
    vids = variants.ids
    refs = {}
    total = 0
    for model, field in REF_MODELS:
        info = _count(model, field, vids)
        refs[model] = info
        total += info["count"]
    if "mrp.production" in env:
        refs["mrp.bom.line"] = (
            _count("mrp.bom.line", "product_id", vids)
            if "mrp.bom.line" in env
            else {"exists": False}
        )
    rows.append(
        {
            "template_id": t.id,
            "variant_ids": vids,
            "name": t.name,
            "default_code": t.default_code or "",
            "barcode": t.barcode or "",
            "type": t.type,
            "uom": t.uom_id.name if t.uom_id else "",
            "uom_id": t.uom_id.id if t.uom_id else None,
            "category": t.categ_id.complete_name if t.categ_id else "",
            "list_price": float(t.list_price or 0),
            "standard_price": float(t.standard_price or 0),
            "company_id": t.company_id.id or False,
            "company_name": t.company_id.name if t.company_id else "",
            "active": bool(t.active),
            "sale_ok": bool(t.sale_ok),
            "purchase_ok": bool(t.purchase_ok),
            "create_date": str(t.create_date),
            "write_date": str(t.write_date),
            "create_uid": t.create_uid.name if t.create_uid else "",
            "description_sale": (t.description_sale or "")[:240],
            "reference_total": total,
            "references": refs,
        }
    )

print("GRAVA_AUDIT_BEGIN")
print(
    json.dumps(
        {"product_count": len(rows), "products": rows},
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
print("GRAVA_AUDIT_END")
