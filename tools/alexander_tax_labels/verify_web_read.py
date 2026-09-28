# ruff: noqa
"""Reproduce the product.template web_read that broke the form."""


def run(env):
    dor = env["res.company"].sudo().search([("dx_short_code", "=", "DOR")], limit=1)
    user = (
        env["res.users"].sudo().search([("login", "=", "fausto@justech.do")], limit=1)
    )
    product = (
        env["product.template"]
        .sudo()
        .search([("name", "ilike", "Windows Server 2025")], limit=1)
    )
    if not product:
        product = (
            env["product.template"].sudo().search([("company_id", "=", False)], limit=1)
        )
    spec = {
        "id": {},
        "name": {},
        "taxes_id": {"fields": {"display_name": {}}},
        "supplier_taxes_id": {"fields": {"display_name": {}}},
        "product_variant_ids": {
            "fields": {"id": {}, "taxes_id": {"fields": {"display_name": {}}}}
        },
    }
    rec = (
        product.with_user(user)
        .with_company(dor)
        .with_context(allowed_company_ids=[dor.id])
    )
    rows = rec.web_read(spec)
    sale = rows[0].get("taxes_id") or []
    names = (
        [row.get("display_name") for row in sale]
        if sale and isinstance(sale[0], dict)
        else sale
    )
    print("WEB_READ", product.id, "sale_chips", names)
    print("WEB_READ_PASS")
    return True


run(env)
