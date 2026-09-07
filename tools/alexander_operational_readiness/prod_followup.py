# ruff: noqa
"""Follow-up read-only: record rules, bancos, RNC, QA invoices."""

import json
import re
from pathlib import Path

OUT = "/tmp/op_ready_followup.json"


def _vat(s):
    return re.sub(r"\D", "", str(s or ""))


def run(env):
    out = {"leaks_restricted_user": {}, "banks": [], "rnc": [], "qa_moves": []}
    User = env["res.users"]
    restricted = User.browse(7)
    # user 7 = DX TEST SECURITY BLU, only company 8
    Move = env["account.move"]
    if restricted.exists():
        env_u = env(user=restricted.id)
        seen = env_u["account.move"].search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice")),
                ("state", "=", "posted"),
            ]
        )
        foreign = seen.filtered(lambda m: m.company_id.id != 8)
        out["leaks_restricted_user"] = {
            "user": restricted.login,
            "allowed": restricted.company_ids.ids,
            "seen_total": len(seen),
            "foreign": len(foreign),
            "foreign_sample": [
                {
                    "id": m.id,
                    "company": m.company_id.name,
                    "ncf": m.justech_do_ncf,
                    "name": m.name,
                }
                for m in foreign[:10]
            ],
            "own_sample": [
                {"id": m.id, "ncf": m.justech_do_ncf, "company": m.company_id.name}
                for m in seen
                if m.company_id.id == 8
            ][:5],
        }
    # Alexander with single-company context via with_company + allowed
    alex = User.search([("login", "=", "inversionesdoralex@gmail.com")], limit=1)
    if alex:
        env_a = env(user=alex.id, context={"allowed_company_ids": [11]})
        seen = env_a["account.move"].search(
            [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
        )
        foreign = seen.filtered(lambda m: m.company_id.id != 11)
        out["leaks_alexander_doralex_only"] = {
            "seen_total": len(seen),
            "foreign": len(foreign),
            "foreign_ncf": [m.justech_do_ncf for m in foreign[:10]],
        }
    for c in env["res.company"].search([("id", "!=", 1)]):
        p = c.partner_id
        banks = env["res.partner.bank"].search(
            ["|", ("partner_id", "=", p.id), ("company_id", "=", c.id)]
        )
        journals = env["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "bank")]
        )
        out["rnc"].append(
            {
                "company": c.name,
                "company_vat": c.vat,
                "partner_vat": p.vat,
                "digits": _vat(c.vat or p.vat),
            }
        )
        out["banks"].append(
            {
                "company": c.name,
                "partner_banks": [
                    {
                        "id": b.id,
                        "acc": b.acc_number,
                        "bank": b.bank_id.name if b.bank_id else "",
                        "company": b.company_id.name,
                    }
                    for b in banks
                ],
                "journals": [
                    {
                        "id": j.id,
                        "name": j.name,
                        "bank_account_id": (
                            j.bank_account_id.id if j.bank_account_id else False
                        ),
                        "acc": (
                            j.bank_account_id.acc_number if j.bank_account_id else ""
                        ),
                    }
                    for j in journals
                ],
            }
        )
    qa_moves = env["account.move"].search(
        [
            ("justech_do_ncf", "=like", "%9910%"),
            ("state", "=", "posted"),
        ]
    )
    out["qa_moves"] = [
        {
            "id": m.id,
            "company": m.company_id.name,
            "name": m.name,
            "ncf": m.justech_do_ncf,
            "partner": m.partner_id.name,
            "total": float(m.amount_total),
            "residual": float(m.amount_residual),
            "origin": m.invoice_origin,
        }
        for m in qa_moves
    ]
    Path(OUT).write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
