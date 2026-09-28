# ruff: noqa
"""Reproduce product create with only Doralex selected. Unlinks the QA product."""

NAME = "DXQA Licencia Windows Server tax-create"


def run(env):
    dor = env["res.company"].sudo().search([("dx_short_code", "=", "DOR")], limit=1)
    user = env["res.users"].sudo().search(
        [("login", "=", "fausto@justech.do")], limit=1
    ) or env["res.users"].sudo().search(
        [("login", "=", "geilin.rosario@inversionesdoralex.com")], limit=1
    )
    leftover = (
        env["product.template"]
        .sudo()
        .with_context(active_test=False)
        .search([("name", "=", NAME)])
    )
    leftover.unlink()
    rec = (
        env["product.template"]
        .with_user(user)
        .with_company(dor)
        .with_context(allowed_company_ids=[dor.id])
        .create(
            {
                "name": NAME,
                "sale_ok": True,
                "purchase_ok": True,
                "list_price": 1.0,
                "taxes_id": [(6, 0, dor.account_sale_tax_id.ids)],
                "supplier_taxes_id": [(6, 0, dor.account_purchase_tax_id.ids)],
            }
        )
    )
    sale = rec.sudo().taxes_id
    purch = rec.sudo().supplier_taxes_id
    print(
        "CREATED",
        rec.id,
        "company",
        rec.company_id.id or "SHARED",
        "sale",
        [(t.id, t.company_id.dx_short_code, t.name) for t in sale],
        "purchase",
        [(t.id, t.company_id.dx_short_code, t.name) for t in purch],
    )
    if not any(t.company_id == dor for t in sale):
        raise SystemExit("MISSING_DOR_SALE")
    if not any(t.company_id == dor for t in purch):
        raise SystemExit("MISSING_DOR_PURCHASE")
    rec.unlink()
    env.cr.commit()
    print("CREATE_ONE_COMPANY=PASS")
    return True


run(env)
