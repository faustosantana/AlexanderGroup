# -*- coding: utf-8 -*-
"""STAGING READ-ONLY: 16% SALE tax structure for reference. Never copy IDs to PROD."""

assert env.cr.dbname == "doralex_ent_staging"
print("STG_ITBIS", env.cr.dbname)
Tax = env["account.tax"].sudo()
for t in Tax.search(
    [("amount", "=", 16.0), ("type_tax_use", "=", "sale")], order="company_id"
):
    group = t.tax_group_id
    print(
        "STG16SALE",
        "co=%s" % t.company_id.id,
        "id=%s" % t.id,
        "name=%r" % t.name,
        "group=%r" % (group.name if group else None),
        "amount_type=%s" % t.amount_type,
        "price_include=%s" % t.price_include,
        "active=%s" % t.active,
        "inv_lines=%s"
        % [
            (
                ln.repartition_type,
                ln.account_id.name if ln.account_id else None,
                ln.account_id.company_ids.ids if ln.account_id else None,
                ",".join(ln.tag_ids.mapped("name")),
            )
            for ln in t.invoice_repartition_line_ids
        ],
    )
print("STG_ITBIS_DONE")
