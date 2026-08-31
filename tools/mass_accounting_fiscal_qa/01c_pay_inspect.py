# -*- coding: utf-8 -*-
p = env["account.payment"].browse(68)
print("PAY", p.id, p.state, p.amount, p.move_id, getattr(p, "outstanding_account_id", None))
print("PAY_FIELDS", [f for f in p._fields if "outstanding" in f or "move" in f or "state" in f or "reconcile" in f])
inv = env["account.move"].search([("ref", "like", "DXQA-MASS-20260831-C11-S-FULL01")], limit=1)
print("INV residual after reg", inv.amount_residual, inv.payment_state)
print("has action_validate", hasattr(p, "action_validate"))
print("has action_post", hasattr(p, "action_post"))
print("has mark_as_sent", hasattr(p, "action_post"))
# company payment accounts
c = env["res.company"].browse(11)
print(
    "company payment-related",
    [
        (f, getattr(c, f, None))
        for f in c._fields
        if "payment" in f or "outstanding" in f or "suspense" in f
    ],
)
# try to find outstanding accounts
Account = env["account.account"].with_company(c)
outs = Account.search(
    [("account_type", "in", ("asset_current", "asset_receivable", "liability_current", "liability_payable")), ("name", "ilike", "outstanding")]
)
print("OUT_ACCOUNTS", [(a.id, a.display_name, a.account_type) for a in outs])
# journal inbound/outbound payment accounts
j = env["account.journal"].browse(76)
print("journal fields", [f for f in j._fields if "outstanding" in f or "suspense" in f or "payment" in f])
for f in j._fields:
    if "outstanding" in f or "suspense" in f:
        print(" J", f, getattr(j, f))
