# ruff: noqa
"""Read-only dump of posted invoice lines for the two Grava 3/4 products."""

import json

ids = [21, 138]
# staging ids differ; search by name
Template = env["product.template"].sudo().with_context(active_test=False)
temps = Template.search(
    [
        "|",
        ("name", "=", "(AGREGADO GRUESO) GRAVA 3/4"),
        ("name", "=", "AGREGADO GRUESO (GRAVA) 3/4"),
    ]
)
vids = temps.product_variant_ids.ids
Line = env["account.move.line"].sudo()
rows = []
for line in Line.search([("product_id", "in", vids)]):
    rows.append(
        {
            "aml_id": line.id,
            "move": line.move_id.name,
            "move_id": line.move_id.id,
            "move_type": line.move_id.move_type,
            "state": line.move_id.state,
            "company": line.move_id.company_id.name,
            "date": str(line.move_id.invoice_date or line.move_id.date),
            "partner": line.move_id.partner_id.name,
            "product_id": line.product_id.id,
            "product_tmpl_id": line.product_id.product_tmpl_id.id,
            "product_name": line.product_id.name,
            "line_name": line.name,
            "qty": float(line.quantity or 0),
            "price_unit": float(line.price_unit or 0),
            "price_subtotal": float(line.price_subtotal or 0),
            "price_total": float(line.price_total or 0),
            "account": line.account_id.code,
        }
    )
print("GRAVA_AML_BEGIN")
print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
print("GRAVA_AML_END")
