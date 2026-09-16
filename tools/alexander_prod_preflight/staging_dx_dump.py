# -*- coding: utf-8 -*-
"""STAGING DX catalog dump for PROD compare. Read-only."""

assert env.cr.dbname == "doralex_ent_staging"
Cat = env["justech.do.withholding.catalog"].sudo().with_context(active_test=False)
print("STAGING_DX_COUNT", Cat.search_count([("code", "like", "DX-")]))
for rec in Cat.search([("code", "like", "DX-")], order="code"):
    print(
        "STG",
        rec.code,
        rec.name,
        "rate=%s" % rec.rate,
        "base=%s" % rec.base_type,
        "pres=%s" % getattr(rec, "dx_presumed_income_pct", None),
        "active=%s" % rec.active,
        "auto_tax=%s" % bool(rec.tax_id),
    )
if "justech.do.withholding.company.config" in env:
    for cfg in env["justech.do.withholding.company.config"].sudo().search([]):
        acc = cfg.account_id
        print(
            "STGCFG",
            cfg.company_id.id,
            cfg.catalog_id.code,
            "code=%s" % (acc.code if acc else None),
            "name=%s" % (acc.name if acc else None),
            "type=%s" % (acc.account_type if acc else None),
            "cos=%s" % (acc.company_ids.ids if acc else None),
        )
for name in (
    "justech_alexander_base",
    "justech_alexander_ux",
    "justech_alexander_reports",
):
    m = env["ir.module.module"].sudo().search([("name", "=", name)], limit=1)
    print("STGMOD", name, m.latest_version)
