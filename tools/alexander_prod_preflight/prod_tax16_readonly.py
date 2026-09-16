# -*- coding: utf-8 -*-
assert env.cr.dbname == "doralex_prod"
print("TAX16_DB", env.cr.dbname)
Tax = env["account.tax"].sudo()
for t in Tax.search([("amount", "=", 16.0)], order="company_id,type_tax_use,name"):
    print("T16", t.company_id.id, t.type_tax_use, t.name, "active=%s" % t.active)
print("TAX16_DONE")
