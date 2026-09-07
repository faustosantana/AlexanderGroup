# ruff: noqa
import json


def run(env):
    out = []
    for q in env["stock.quant"].search([("quantity", "!=", 0)]):
        out.append(
            {
                "id": q.id,
                "product": q.product_id.display_name,
                "code": q.product_id.default_code,
                "location": q.location_id.complete_name,
                "qty": float(q.quantity),
                "company": q.company_id.name,
                "product_active": q.product_id.active,
            }
        )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
