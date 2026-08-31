# -*- coding: utf-8 -*-
"""Create missing vendor credit notes for DXQA-MASS bills. Staging only."""

TAG = "DXQA-MASS-20260831"
CN_DATE = "2026-08-22"
ctx = {
    "mail_notrack": True,
    "tracking_disable": True,
    "justech_approval_skip": True,
}

created = []
errors = []
for company in env["res.company"].search([("active", "=", True)], order="id"):
    e = env(context=dict(env.context, allowed_company_ids=[company.id], **ctx))
    purch_j = e["account.journal"].search(
        [
            ("company_id", "=", company.id),
            ("type", "=", "purchase"),
            ("active", "=", True),
        ],
        limit=1,
    )
    bills = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            "|",
            ("ref", "like", "%s-C%s-B-CNPART" % (TAG, company.id)),
            ("ref", "like", "%s-C%s-B-CNFULL" % (TAG, company.id)),
        ]
    )
    for bill in bills:
        existing = e["account.move"].search(
            [("reversed_entry_id", "=", bill.id)], limit=1
        )
        if existing:
            continue
        key = (bill.ref or "").split("-")[-1]
        seq = 100 if "CNPART" in key else 200
        num = int("".join(ch for ch in key if ch.isdigit()) or "1")
        ncf = "B04%02d%02d%04d" % (88, company.id, seq + num)
        fraction = 0.3 if "CNPART" in key else 1.0
        try:
            with e.cr.savepoint():
                Reversal = e["account.move.reversal"]
                vals = {
                    "reason": "%s vendor CN" % TAG,
                    "date": CN_DATE,
                    "journal_id": purch_j.id,
                    "move_ids": [(6, 0, bill.ids)],
                    "justech_vendor_cn_ncf": ncf,
                    "justech_vendor_cn_date": CN_DATE,
                }
                if "company_id" in Reversal._fields:
                    vals["company_id"] = company.id
                rev = Reversal.with_context(
                    active_model="account.move",
                    active_ids=bill.ids,
                    active_id=bill.id,
                ).create(vals)
                action = rev.refund_moves()
                cn = e["account.move"]
                if isinstance(action, dict) and action.get("res_id"):
                    cn = e["account.move"].browse(action["res_id"])
                if not cn:
                    cn = e["account.move"].search(
                        [("reversed_entry_id", "=", bill.id)], order="id desc", limit=1
                    )
                if cn and fraction < 1.0 and cn.state == "draft":
                    for line in cn.invoice_line_ids:
                        line.price_unit = line.price_unit * fraction
                    cn.action_post()
                elif cn and cn.state == "draft":
                    cn.action_post()
                created.append((company.id, bill.id, cn.id if cn else None, ncf))
                print("CN_OK", company.id, bill.ref, cn.id if cn else None, ncf)
        except Exception as exc:
            errors.append((company.id, bill.ref, "%s: %s" % (type(exc).__name__, exc)))
            print("CN_FAIL", company.id, bill.ref, type(exc).__name__, exc)
    e.cr.commit()

print("CREATED", len(created), "ERRORS", len(errors))
