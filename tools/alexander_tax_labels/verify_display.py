# ruff: noqa
"""Confirm product form shows only the current company's ITBIS chips."""


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
            env["product.template"]
            .sudo()
            .search([("name", "ilike", "Windows Server")], limit=1)
        )
    print("PRODUCT", product.id, product.name)
    stored_sale = product.sudo().taxes_id
    print(
        "STORED_SALE",
        len(stored_sale),
        [(t.company_id.dx_short_code, t.name) for t in stored_sale],
    )
    rec = (
        product.with_user(user)
        .with_company(dor)
        .with_context(allowed_company_ids=[dor.id])
    )
    visible = rec._dx_visible_product_taxes("taxes_id")
    purch = rec._dx_visible_product_taxes("supplier_taxes_id")
    print("VISIBLE_SALE", [(t.id, t.name) for t in visible])
    print("VISIBLE_PURCHASE", [(t.id, t.name) for t in purch])
    data = rec.read(["taxes_id", "supplier_taxes_id"])[0]
    print("READ_SALE", data["taxes_id"])
    print("READ_PURCHASE", data["supplier_taxes_id"])
    if set(data["taxes_id"]) != set(visible.ids):
        raise SystemExit("READ_SALE_MISMATCH")
    if set(data["supplier_taxes_id"]) != set(purch.ids):
        raise SystemExit("READ_PURCHASE_MISMATCH")
    if any(t.company_id != dor for t in visible):
        raise SystemExit("FOREIGN_SALE_VISIBLE")
    if any(t.company_id != dor for t in purch):
        raise SystemExit("FOREIGN_PURCHASE_VISIBLE")
    if len(stored_sale) < 2:
        print("STORED_NOT_MIRRORED_WARN")
    print("DISPLAY_ONE_COMPANY=PASS")
    return True


run(env)
