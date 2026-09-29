# ruff: noqa
"""Confirm quotation date is visible on the sale form. Read-only."""


def run(env):
    so = env["sale.order"].sudo().search([("name", "=", "REM/SO/00009")], limit=1)
    if not so:
        so = env["sale.order"].sudo().search([("state", "=", "draft")], limit=1)
    user = env["res.users"].sudo().search(
        [("login", "=", "elianny.sanchez@inversionesdoralex.com")], limit=1
    )
    if not user:
        user = env["res.users"].sudo().browse(15)
    rec = so.with_user(user).with_company(so.company_id).with_context(
        allowed_company_ids=[so.company_id.id]
    )
    arch = rec.env["sale.order"].get_view(view_type="form").get("arch") or ""
    print("SO", so.name, "state", so.state, "date_order", so.date_order)
    q_hidden = 'string="Quotation Date"' in arch and "invisible=\"1\"" in arch
    print("ARCH_HAS_FECHA_LABEL", ">Fecha<" in arch or 'string="Fecha"' in arch)
    print("ARCH_HAS_GROUP_NO_ONE", "group_no_one" in arch)
    # quotation date field should not be unconditionally invisible
    i = arch.find('name="date_order"')
    print("FIRST_DATE_ORDER_SNIP", arch[max(0, i - 120) : i + 220].replace("\n", " "))
    dx = so._dx_sale_compose()
    print("PDF_DATE", dx.get("date"), "PDF_VALIDITY", dx.get("validity"))
    return True


run(env)
