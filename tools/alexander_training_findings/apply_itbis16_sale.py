# ruff: noqa
"""STAGING/DEV only: create sale 16% ITBIS per company if missing.

Copies accounts from that company's sale 18% ITBIS. Does not assign products.
Does not touch posted invoices. Never run on production.
"""

import json

if env.cr.dbname not in {"doralex_ent_staging", "doralex_dev"}:
    raise RuntimeError("Refuse to create taxes outside DEV/STAGING: %s" % env.cr.dbname)

Tax = env["account.tax"].sudo()
created = []
skipped = []
for company in env["res.company"].sudo().search([]):
    if "plantilla" in (company.name or "").lower():
        continue
    existing = Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 16.0),
            ("amount_type", "=", "percent"),
            ("active", "=", True),
        ],
        limit=1,
    )
    if existing:
        skipped.append({"company": company.name, "tax_id": existing.id})
        continue
    template = Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 18.0),
            ("name", "ilike", "ITBIS"),
            ("active", "=", True),
        ],
        limit=1,
    )
    if not template:
        skipped.append(
            {"company": company.name, "reason": "no sale 18% ITBIS template"}
        )
        continue
    copy = template.copy(
        {
            "name": "16% ITBIS",
            "amount": 16.0,
            "description": "16% ITBIS Sales",
        }
    )
    created.append(
        {
            "company": company.name,
            "tax_id": copy.id,
            "from_tax_id": template.id,
            "price_include": copy.price_include,
        }
    )

print(
    json.dumps({"created": created, "skipped": skipped}, ensure_ascii=False, indent=2)
)
env.cr.commit()
