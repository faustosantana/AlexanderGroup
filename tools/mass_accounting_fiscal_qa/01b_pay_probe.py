# -*- coding: utf-8 -*-
ctx = {
    "mail_notrack": True,
    "tracking_disable": True,
    "justech_approval_skip": True,
    "allowed_company_ids": [11],
}
env = env(context=dict(env.context, **ctx))
company = env["res.company"].browse(11)
Move = env["account.move"].with_company(company)
inv = Move.search([("ref", "like", "DXQA-MASS-20260831-C11-S-FULL01")], limit=1)
print("INV", inv.id, inv.state, inv.amount_residual, inv.payment_state, inv.partner_id.id)
print(
    "INV_LINES",
    [
        (l.account_id.display_name, l.account_id.account_type, l.balance, l.amount_residual, l.reconciled)
        for l in inv.line_ids
    ],
)
bank = env["account.journal"].search(
    [("company_id", "=", 11), ("type", "=", "bank")], limit=1
)
method = env["account.payment.method.line"].search(
    [("journal_id", "=", bank.id), ("payment_method_id.payment_type", "=", "inbound")],
    limit=1,
)
print("BANK", bank.id, bank.name, "METHOD", method.id, method.name, method.payment_account_id)
print("OUTSTANDING inbound", getattr(company, "account_journal_payment_debit_account_id", None))
print("company fields", [f for f in company._fields if "outstanding" in f or "payment_debit" in f or "payment_credit" in f])

# try payment.register
Register = env["account.payment.register"].with_context(
    active_model="account.move", active_ids=inv.ids
)
wiz = Register.create(
    {
        "journal_id": bank.id,
        "payment_date": "2026-08-20",
        "amount": 1000,
        "communication": "DXQA-PAYPROBE-REG",
    }
)
print("REG fields payment_method", wiz.payment_method_line_id.id if wiz.payment_method_line_id else None)
try:
    action = wiz.action_create_payments()
    print("REG_ACTION", action)
    pays = env["account.payment"].search([("memo", "=", "DXQA-PAYPROBE-REG")]) or env[
        "account.payment"
    ].search([("payment_reference", "=", "DXQA-PAYPROBE-REG")])
    if not pays and isinstance(action, dict) and action.get("res_id"):
        pays = env["account.payment"].browse(action["res_id"])
    print("REG_PAY", pays)
    for p in pays:
        print("PAY", p.id, p.state, p.amount, p.move_id.id)
        print(
            "PAY_LINES",
            [
                (
                    l.account_id.display_name,
                    l.account_id.account_type,
                    l.balance,
                    l.reconciled,
                    l.amount_residual,
                )
                for l in p.move_id.line_ids
            ],
        )
except Exception as e:
    print("REG_FAIL", type(e).__name__, e)
    env.cr.rollback()

# try multi wizard
try:
    W = env["multi.invoice.manual.payment.wizard"]
    mw = W.create(
        {
            "partner_type": "customer",
            "partner_id": inv.partner_id.id,
            "company_id": 11,
            "payment_date": "2026-08-20",
            "journal_id": bank.id,
            "payment_method_line_id": method.id,
            "ref": "DXQA-PAYPROBE-MULTI",
            "amount_received": 500,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "move_id": inv.id,
                        "currency_id": inv.currency_id.id,
                        "invoice_date": inv.invoice_date,
                        "due_date": inv.invoice_date_due,
                        "amount_total": abs(inv.amount_total),
                        "amount_residual": abs(inv.amount_residual),
                        "amount_to_apply": 500,
                    },
                )
            ],
        }
    )
    action = mw.action_create_payment()
    print("MULTI_OK", action)
except Exception as e:
    print("MULTI_FAIL", type(e).__name__, e)
    env.cr.rollback()

env.cr.commit()
print("PROBE_PAY_DONE")
