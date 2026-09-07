"""Read-only dump of current product catalog for matching."""

import json

Template = (
    env["product.template"]
    .sudo()
    .with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
)
rows = []
for t in Template.search([]):
    name = t.name or ""
    if "DXQA" in name.upper() or "DX TEST" in name.upper() or "DX-TEST" in name.upper():
        continue
    rows.append(
        {
            "id": t.id,
            "product_variant_id": t.product_variant_id.id,
            "name": name,
            "default_code": t.default_code or "",
            "barcode": t.barcode or "",
            "type": t.type,
            "list_price": float(t.list_price or 0),
            "standard_price": float(t.standard_price or 0),
            "sale_ok": bool(t.sale_ok),
            "purchase_ok": bool(t.purchase_ok),
            "uom": t.uom_id.name if t.uom_id else "",
            "categ": t.categ_id.complete_name if t.categ_id else "",
            "company_id": t.company_id.id or False,
            "company_name": t.company_id.name if t.company_id else "",
            "description_sale": (t.description_sale or "")[:240],
        }
    )
print(
    json.dumps(
        {"count": len(rows), "products": rows},
        ensure_ascii=False,
        indent=2,
    )
)
