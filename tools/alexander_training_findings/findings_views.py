# ruff: noqa
import json

rows = []
View = env["ir.ui.view"].sudo()
for v in View.search(
    [
        ("model", "in", ("product.template", "sale.order")),
        ("key", "ilike", "product_template"),
    ]
):
    rows.append(
        {"xmlid": v.get_external_id().get(v.id), "name": v.name, "model": v.model}
    )
print(json.dumps(rows[:40], ensure_ascii=False, indent=2))
print("---")
for xmlid in (
    "stock.product_template_form_view",
    "stock.view_template_property_form",
    "product.product_template_form_view",
    "product.product_template_only_form_view",
    "sale.view_quotation_tree",
    "sale.view_sales_order_filter",
    "sale.view_order_form",
    "sale.action_report_pro_forma_invoice",
):
    rec = env.ref(xmlid, raise_if_not_found=False)
    print(xmlid, "OK" if rec else "MISSING")
