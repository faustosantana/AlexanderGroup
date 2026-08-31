# -*- coding: utf-8 -*-
ctx = {
    "mail_notrack": True,
    "tracking_disable": True,
    "justech_approval_skip": True,
    "allowed_company_ids": [11],
    "force_payment_move": True,
}
env = env(context=dict(env.context, **ctx))
company = env["res.company"].browse(11)
inv = env["account.move"].search(
    [("ref", "=", "DXQA-MASS-20260831-C11-S-FULL01")], limit=1
)
print("INV", inv.id, inv.amount_residual, inv.payment_state)
bank = env["account.journal"].search(
    [("company_id", "=", 11), ("type", "=", "bank")], limit=1
)
method = env["account.payment.method.line"].search(
    [("journal_id", "=", bank.id), ("payment_method_id.payment_type", "=", "inbound")],
    limit=1,
)
print("TRANSFER", company.transfer_account_id)
try:
    dummy = env["account.payment"].new({"company_id": 11, "payment_type": "inbound"})
    acc = dummy._get_outstanding_account("inbound")
    print("GET_OUTSTANDING", acc, acc.display_name if acc else None)
except Exception as e:
    print("GET_OUTSTANDING_FAIL", type(e).__name__, e)

W = env["multi.invoice.manual.payment.wizard"]
try:
    mw = W.create(
        {
            "partner_type": "customer",
            "partner_id": inv.partner_id.id,
            "company_id": 11,
            "payment_date": "2026-08-20",
            "journal_id": bank.id,
            "payment_method_line_id": method.id,
            "ref": "DXQA-PAYPROBE-FORCE",
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
    pay = env["account.payment"].browse(action.get("res_id"))
    print(
        "MULTI_OK",
        pay.id,
        pay.state,
        pay.move_id,
        pay.amount,
        "applied",
        len(pay.justech_applied_invoice_ids),
    )
    if pay.move_id:
        print(
            "LINES",
            [
                (l.account_id.display_name, l.account_id.account_type, l.balance, l.reconciled)
                for l in pay.move_id.line_ids
            ],
        )
    inv.invalidate_recordset()
    print("INV_AFTER", inv.amount_residual, inv.payment_state)
    env.cr.commit()
except Exception as e:
    print("MULTI_FAIL", type(e).__name__, e)
    env.cr.rollback()
