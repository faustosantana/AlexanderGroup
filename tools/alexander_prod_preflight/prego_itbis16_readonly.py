# -*- coding: utf-8 -*-
"""PROD READ-ONLY: ITBIS 16/18 sale vs purchase. Never commit."""

assert env.cr.dbname == "doralex_prod"
print("PREGO_ITBIS", env.cr.dbname)


def _rep_lines(tax, field):
    lines = getattr(tax, field, False)
    if not lines:
        return []
    out = []
    for line in lines:
        acc = line.account_id
        tags = (
            ",".join(line.tag_ids.mapped("name")) if "tag_ids" in line._fields else ""
        )
        out.append(
            {
                "factor": getattr(line, "factor_percent", None),
                "repartition_type": getattr(line, "repartition_type", None),
                "account_id": acc.id if acc else False,
                "account_code": acc.code if acc else False,
                "account_name": acc.name if acc else False,
                "account_cos": acc.company_ids.ids if acc else [],
                "tags": tags,
            }
        )
    return out


def _dump_tax(label, t):
    group = t.tax_group_id
    print(
        "TAX",
        label,
        "id=%s" % t.id,
        "co=%s" % t.company_id.id,
        "name=%r" % t.name,
        "amount=%s" % t.amount,
        "use=%s" % t.type_tax_use,
        "active=%s" % t.active,
        "price_include=%s" % t.price_include,
        "include_base=%s" % getattr(t, "include_base_amount", None),
        "amount_type=%s" % t.amount_type,
        "group_id=%s" % (group.id if group else None),
        "group=%r" % (group.name if group else None),
        "invoice_repartition=%s" % _rep_lines(t, "invoice_repartition_line_ids"),
        "refund_repartition=%s" % _rep_lines(t, "refund_repartition_line_ids"),
    )


Tax = env["account.tax"].sudo()
ops = env["res.company"].sudo().search([("id", "!=", 1)], order="id")
for company in ops:
    print("=== COMPANY", company.id, company.name, "===")
    sale16 = Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 16.0),
        ]
    )
    purch16 = Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "purchase"),
            ("amount", "=", 16.0),
        ]
    )
    sale18 = Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 18.0),
            ("name", "ilike", "ITBIS"),
        ]
    )
    print(
        "SUMMARY",
        company.id,
        "sale16=%s" % len(sale16),
        "purch16=%s" % len(purch16),
        "sale18_itbis=%s" % len(sale18),
    )
    for t in purch16:
        _dump_tax("PURCH16", t)
    for t in sale16:
        _dump_tax("SALE16", t)
    for t in sale18:
        if "ITBIS" in (t.name or "").upper() or t.name == "18% ITBIS":
            _dump_tax("SALE18", t)

# product default assignment of 16 sale
if "product.template" in env:
    print(
        "PROD_TMPL_16SALE",
        env["product.template"]
        .sudo()
        .search_count([("taxes_id.name", "ilike", "16% ITBIS")]),
    )
print("PREGO_ITBIS_DONE")
