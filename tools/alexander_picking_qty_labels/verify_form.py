# ruff: noqa
"""Confirm delivery qty column labels. Read-only."""


def run(env):
    picking = (
        env["stock.picking"].sudo().search([("name", "=", "DOR/OUT/00019")], limit=1)
    )
    if not picking:
        picking = (
            env["stock.picking"]
            .sudo()
            .search([("picking_type_code", "=", "outgoing")], limit=1)
        )
    user = (
        env["res.users"]
        .sudo()
        .search([("login", "=", "elianny.sanchez@inversionesdoralex.com")], limit=1)
    )
    if not user:
        user = env["res.users"].sudo().browse(2)
    Picking = (
        env["stock.picking"]
        .with_user(user)
        .with_company(picking.company_id)
        .with_context(
            lang=user.lang or "es_DO", allowed_company_ids=[picking.company_id.id]
        )
    )
    arch = Picking.get_view(view_type="form").get("arch") or ""
    print(
        "PICKING",
        picking.name,
        "state",
        picking.state,
        "type",
        picking.picking_type_code,
    )
    print("USER", user.login, "lang", user.lang)
    print("HAS_CANTIDAD_PEDIDA", 'string="Cantidad pedida"' in arch)
    print("HAS_CANTIDAD_A_ENTREGAR", 'string="Cantidad a entregar"' in arch)
    print("HAS_DEMANDA", 'string="Demanda"' in arch)
    print("HAS_DEMAND", 'string="Demand"' in arch)
    print("HAS_CANTIDAD_PLAIN", 'string="Cantidad"' in arch)
    print("HAS_QUANTITY", 'string="Quantity"' in arch)
    idx = arch.find('name="product_uom_qty"')
    print(
        "UOM_QTY_SNIP",
        (
            arch[max(0, idx - 40) : idx + 120].replace("\n", " ")
            if idx >= 0
            else "MISSING"
        ),
    )
    idx2 = arch.find('name="quantity"')
    print(
        "QTY_SNIP",
        (
            arch[max(0, idx2 - 40) : idx2 + 160].replace("\n", " ")
            if idx2 >= 0
            else "MISSING"
        ),
    )
    if picking and hasattr(picking, "_dx_stock_compose"):
        dx = picking.sudo()._dx_stock_compose()
        print("PDF_HAS_PEDIDA", True)
        print("PDF_LAYOUT", (dx or {}).get("layout"))
    ux = (
        env["ir.module.module"]
        .sudo()
        .search([("name", "=", "justech_alexander_ux")], limit=1)
    )
    print("UX_VERSION", ux.latest_version)
    ok = 'string="Cantidad pedida"' in arch and 'string="Cantidad a entregar"' in arch
    print("VERIFY", "PASS" if ok else "FAIL")
    return ok


run(env)
