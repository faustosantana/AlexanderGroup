# -*- coding: utf-8 -*-
"""PROD READ-ONLY: DX account uniqueness per company+name+type. Never commit."""

assert env.cr.dbname == "doralex_prod"
print("PREGO_DX", env.cr.dbname)

RULES = (
    ("DX-ISR-ESTADO-5", "Other Withholdings (N07-07)", "liability_non_current"),
    ("DX-ISR-PROF-PF-15", "Other Withholdings (N07-07)", "liability_non_current"),
    ("DX-ISR-TEC-PF-15", "Other Withholdings (N07-07)", "liability_non_current"),
    (
        "DX-ISR-ALQ-PF-15",
        "ISR withheld on rent paid to individuals",
        "liability_non_current",
    ),
    (
        "DX-ITBIS-30-PJ",
        "ITBIS Withheld from Legal Entity (N02-05)",
        "liability_non_current",
    ),
    (
        "DX-ITBIS-100-PF",
        "ITBIS Withheld from Individuals (R293-11)",
        "liability_non_current",
    ),
    (
        "DX-ITBIS-100-SEG",
        "ITBIS Withheld for Professional Services (N02-05)",
        "liability_non_current",
    ),
    (
        "DX-ITBIS-100-ESFL",
        "ITBIS Withheld from Non-Profit Entities (N01-11)",
        "liability_non_current",
    ),
    (
        "DX-ITBIS-100-INF",
        "ITBIS Withheld from Informal Goods (N08-10)",
        "liability_non_current",
    ),
    ("DX-ISR-DIV-10", "Other Withholdings", "liability_non_current"),
    ("DX-ISR-INT-PF-10", "ISR withheld on interest paid", "liability_non_current"),
    (
        "DX-ISR-INT-EXT-10",
        "ISR Withheld on Interest Paid Abroad",
        "liability_non_current",
    ),
    (
        "DX-ISR-EXT-REG-15",
        "ISR Withheld on Remittances Abroad (L253-12)",
        "liability_non_current",
    ),
    (
        "DX-ISR-EXT-SW-15",
        "ISR Withheld on Remittances Abroad (L253-12)",
        "liability_non_current",
    ),
    (
        "DX-ISR-EXT-ADS-15",
        "ISR Withheld on Remittances Abroad (L253-12)",
        "liability_non_current",
    ),
    (
        "DX-ISR-EXT-DATA-15",
        "ISR Withheld on Remittances Abroad (L253-12)",
        "liability_non_current",
    ),
    (
        "DX-ISR-EXT-27",
        "ISR Withheld on Remittances Abroad (L253-12)",
        "liability_non_current",
    ),
    ("DX-ISR-PREMIO-25", "Other Withholdings", "liability_non_current"),
    ("DX-ISR-OTRAS-15", "Other Withholdings (N07-07)", "liability_non_current"),
)

Account = env["account.account"].sudo()
ops = env["res.company"].sudo().search([("id", "!=", 1)], order="id")
fail = 0
for company in ops:
    for code, name, atype in RULES:
        recs = Account.search(
            [
                ("company_ids", "in", [company.id]),
                ("name", "=", name),
                ("account_type", "=", atype),
            ]
        )
        foreign = []
        ids = []
        for acc in recs:
            ids.append(acc.id)
            others = [i for i in acc.company_ids.ids if i != company.id]
            if others:
                foreign.append((acc.id, others))
        result = "OK" if len(recs) == 1 and not foreign else "BLOCKER"
        if result != "OK":
            fail += 1
        print(
            "DXMAP",
            "co=%s" % company.id,
            "rule=%s" % code,
            "name=%s" % name,
            "type=%s" % atype,
            "candidates=%s" % len(recs),
            "ids=%s" % ids,
            "foreign=%s" % foreign,
            "result=%s" % result,
        )
print("DXMAP_FAILS", fail)
print("PREGO_DX_DONE")
