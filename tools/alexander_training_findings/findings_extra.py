# ruff: noqa
"""READ-ONLY extras: padrón, recovery members, sale 16/18 taxes, description mismatches."""

import json

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}

padron = {}
if "justech.do.rnc.padron" in env:
    P = env["justech.do.rnc.padron"].sudo()
    padron["count"] = P.search_count([])
    if "write_date" in P._fields:
        last = P.search([], order="write_date desc", limit=1)
        padron["last_write"] = str(last.write_date) if last else ""
    if "justech.do.rnc.padron.config" in env:
        cfgs = env["justech.do.rnc.padron.config"].sudo().search([])
        padron["configs"] = [
            {
                "id": c.id,
                "name": c.display_name,
                **{
                    f: str(c[f])
                    for f in c._fields
                    if f
                    in (
                        "active",
                        "last_update",
                        "last_sync",
                        "source",
                        "state",
                        "auto_update",
                    )
                },
            }
            for c in cfgs
        ]

recovery_users = []
g = env.ref(
    "justech_accounting_recovery.group_accounting_recovery", raise_if_not_found=False
)
if g:
    users_field = "user_ids" if "user_ids" in g._fields else "users"
    for u in g[users_field]:
        recovery_users.append({"login": u.login, "name": u.name, "active": u.active})

sale_taxes = []
Tax = env["account.tax"].sudo().with_context(**ctx)
for t in Tax.search([("type_tax_use", "=", "sale"), ("active", "=", True)]):
    sale_taxes.append(
        {
            "id": t.id,
            "name": t.name,
            "amount": t.amount,
            "company": t.company_id.name,
            "company_id": t.company_id.id,
            "price_include": t.price_include,
            "invoice_accounts": [
                l.account_id.code if l.account_id else ""
                for l in t.invoice_repartition_line_ids
                if l.repartition_type == "tax"
            ],
            "refund_accounts": [
                l.account_id.code if l.account_id else ""
                for l in t.refund_repartition_line_ids
                if l.repartition_type == "tax"
            ],
        }
    )

mismatch = []
Sol = env["sale.order.line"].sudo().with_context(**ctx)
for line in Sol.search(
    [("display_type", "=", False), ("product_id", "!=", False)],
    order="id desc",
    limit=40,
):
    tmpl = line.product_id.product_tmpl_id
    desc = (tmpl.description_sale or "").strip()
    if not desc:
        continue
    if desc not in (line.name or ""):
        mismatch.append(
            {
                "line": line.id,
                "so": line.order_id.name,
                "product": line.product_id.display_name,
                "desc_sale": desc[:120],
                "line_name": (line.name or "")[:160],
            }
        )

proforma_group = env.ref("sale.group_proforma_sales", raise_if_not_found=False)
proforma_users = []
if proforma_group:
    uf = "user_ids" if "user_ids" in proforma_group._fields else "users"
    proforma_users = [u.login for u in proforma_group[uf]]

print(
    json.dumps(
        {
            "PADRON": padron,
            "RECOVERY_USERS": recovery_users,
            "SALE_TAXES": sale_taxes,
            "DESC_MISMATCH": mismatch,
            "PROFORMA_USERS": proforma_users,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
