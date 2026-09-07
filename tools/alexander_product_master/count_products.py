# ruff: noqa
import json

Template = env["product.template"].sudo().with_context(active_test=False)
rows = Template.search(
    [("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")]
)
print(
    json.dumps(
        {
            "count": len(rows),
            "shared": len(rows.filtered(lambda t: not t.company_id)),
            "with_company": len(rows.filtered(lambda t: t.company_id)),
        }
    )
)
