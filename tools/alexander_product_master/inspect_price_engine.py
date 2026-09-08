# ruff: noqa
"""Read-only precheck of the Odoo 19 sale-price engine on this runtime."""

import json

ctx = {"allowed_company_ids": env["res.company"].sudo().search([]).ids}
companies = [
    {"id": c.id, "name": c.name, "currency": c.currency_id.name}
    for c in env["res.company"].sudo().search([])
]
version = getattr(release, "version", None) if "release" in dir() else None
try:
    from odoo.release import version as odoo_version
except Exception:
    odoo_version = version or "unknown"

Template = env["product.template"]
SOL = env["sale.order.line"]
price_fields = Template.fields_get(["list_price", "lst_price", "standard_price"])
sol_fields = SOL.fields_get(["price_unit", "discount", "pricelist_item_id", "technical_price_unit"])

mro = [cls.__name__ for cls in type(SOL)._name_class.mro()] if False else []
sol_cls = type(env["sale.order.line"])
sol_mro = [c.__module__ + "." + c.__name__ for c in sol_cls.mro() if hasattr(c, "__module__")]
price_methods = [
    name
    for name in (
        "_compute_price_unit",
        "_get_display_price",
        "_get_pricelist_price",
        "product_id_change",
        "_onchange_product_id",
        "_compute_pricelist_item_id",
    )
    if hasattr(sol_cls, name)
]
method_owners = {}
for name in price_methods:
    func = getattr(sol_cls, name)
    method_owners[name] = getattr(func, "__module__", "") + "." + getattr(func, "__qualname__", name)

overrides = []
for name in price_methods:
    owner = method_owners.get(name, "")
    if "justech" in owner.lower() or "alexander" in owner.lower():
        overrides.append({"method": name, "owner": owner})

# Any custom inherit that mentions price_unit write/compute
for model_name in ("sale.order.line", "product.template", "product.product", "product.pricelist"):
    Model = env[model_name]
    cls = type(Model)
    for attr in dir(cls):
        if "price" not in attr.lower():
            continue
        obj = getattr(cls, attr, None)
        mod = getattr(obj, "__module__", "") or ""
        if any(k in mod.lower() for k in ("justech", "alexander")):
            overrides.append({"model": model_name, "attr": attr, "module": mod})

Pricelist = env["product.pricelist"].sudo().with_context(**ctx)
pricelists = []
for pl in Pricelist.search([("active", "=", True)]):
    item_count = env["product.pricelist.item"].sudo().search_count(
        [("pricelist_id", "=", pl.id)]
    )
    pricelists.append(
        {
            "id": pl.id,
            "name": pl.name,
            "company": pl.company_id.name if pl.company_id else "",
            "currency": pl.currency_id.name if pl.currency_id else "",
            "selectable": bool(getattr(pl, "selectable", True)),
            "item_count": item_count,
        }
    )

mods = env["ir.module.module"].sudo().search(
    [
        ("state", "=", "installed"),
        "|",
        "|",
        ("name", "ilike", "justech"),
        ("name", "ilike", "margin"),
        ("name", "ilike", "pricelist"),
    ]
)
installed = [{"name": m.name, "shortdesc": m.shortdesc} for m in mods]

audit_rules = []
if "justech.audit.rule" in env:
    for r in env["justech.audit.rule"].sudo().search([]):
        if r.model_name in {
            "sale.order",
            "sale.order.line",
            "product.template",
            "product.product",
        }:
            audit_rules.append(
                {
                    "name": r.name,
                    "model": r.model_name,
                    "active": bool(r.active),
                    "audit_write": bool(r.audit_write),
                    "audit_create": bool(r.audit_create),
                }
            )

price_unit_meta = sol_fields.get("price_unit") or {}
list_price_meta = price_fields.get("list_price") or {}

# Default pricelist per company
company_pl = []
for c in env["res.company"].sudo().search([]):
    pl = False
    if "property_product_pricelist" in env["res.partner"]._fields:
        pass
    company_pl.append(
        {
            "company": c.name,
            "currency": c.currency_id.name,
        }
    )

db = env.cr.dbname
print(
    json.dumps(
        {
            "DATABASE": db,
            "ODOO_VERSION": odoo_version,
            "COMPANIES": companies,
            "SALE_PRICE_FIELD": "product.template.list_price",
            "SALE_PRICE_FIELD_META": {
                "type": list_price_meta.get("type"),
                "string": list_price_meta.get("string"),
                "readonly": list_price_meta.get("readonly"),
                "store": list_price_meta.get("store"),
                "related": list_price_meta.get("related"),
                "compute": list_price_meta.get("compute"),
            },
            "PRICE_UNIT_FIELD_META": {
                "type": price_unit_meta.get("type"),
                "string": price_unit_meta.get("string"),
                "readonly": price_unit_meta.get("readonly"),
                "store": price_unit_meta.get("store"),
                "related": price_unit_meta.get("related"),
                "compute": price_unit_meta.get("compute"),
                "inverse": price_unit_meta.get("inverse"),
                "depends": price_unit_meta.get("depends"),
            },
            "PRICE_UNIT_METHODS": method_owners,
            "CUSTOM_PRICE_OVERRIDES_FOUND": overrides,
            "ACTIVE_PRICELISTS": pricelists,
            "INSTALLED_PRICE_RELATED_MODULES": installed,
            "AUDIT_RULES": audit_rules,
            "SOL_PRICE_FIELDS": sorted(
                n for n in SOL.fields_get() if "price" in n or "pricelist" in n or n == "discount"
            ),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
