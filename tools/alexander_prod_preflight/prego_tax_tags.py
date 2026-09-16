# -*- coding: utf-8 -*-
assert env.cr.dbname == "doralex_prod"
Tag = env["account.account.tag"].sudo()
for name in ("base.16%", "tax.16%", "base.18%", "tax.18%"):
    recs = Tag.search([("name", "=", name)])
    print(
        "TAG",
        name,
        "count=%s" % len(recs),
        [
            (t.id, t.country_id.code if t.country_id else None, t.applicability)
            for t in recs
        ],
    )
Acc = env["account.account"].sudo()
for cid, aid in ((8, 1883), (9, 2171), (10, 2459), (11, 2747), (12, 3035), (13, 3323)):
    a = Acc.browse(aid)
    print(
        "SALE_ITBIS_ACC",
        "want_co=%s" % cid,
        "id=%s" % a.id,
        "name=%s" % a.name,
        "type=%s" % a.account_type,
        "cos=%s" % a.company_ids.ids,
        "ok=%s" % (a.company_ids.ids == [cid]),
    )
print("TAGS_DONE")
