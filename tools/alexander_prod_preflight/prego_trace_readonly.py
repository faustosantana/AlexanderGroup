# -*- coding: utf-8 -*-
"""PROD READ-ONLY: trace module registry vs file. Never commit."""

assert env.cr.dbname == "doralex_prod"
m = (
    env["ir.module.module"]
    .sudo()
    .search([("name", "=", "justech_sale_purchase_trace")], limit=1)
)
print("TRACE_STATE", m.state)
print("TRACE_LATEST", m.latest_version)
print("TRACE_INSTALLED", m.installed_version)
print("TRACE_SHORDESC", m.shortdesc)
# models present
print("HAS_QTY_ASSIGN", "justech.sale.purchase.qty.assignment" in env)
print(
    "TRACE_MODELS",
    [x for x in env if "justech" in x and "trace" in x or "qty.assignment" in x],
)
# views from the module
View = env["ir.ui.view"].sudo()
views = View.search(
    [("model", "in", ["sale.order", "account.move"]), ("name", "ilike", "trace")]
)
print(
    "TRACE_VIEWS",
    [(v.id, v.name, v.xml_id if hasattr(v, "xml_id") else v.key) for v in views[:30]],
)
data = (
    env["ir.model.data"]
    .sudo()
    .search([("module", "=", "justech_sale_purchase_trace")], order="model,name")
)
print("TRACE_XMLID_COUNT", len(data))
print("TRACE_XMLID_MODELS", sorted(set(data.mapped("model"))))
print("PREGO_TRACE_DONE")
