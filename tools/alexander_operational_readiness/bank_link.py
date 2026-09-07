# ruff: noqa
"""Enlaza journals Banreservas con res.partner.bank ya existente. No cambia números."""

import json
from pathlib import Path

OUT = "/tmp/op_ready_bank_link.json"


def run(env):
    out = {"linked": [], "skipped": []}
    for c in env["res.company"].search([("id", "!=", 1)]):
        banks = env["res.partner.bank"].search(
            [
                ("partner_id", "=", c.partner_id.id),
                ("acc_number", "!=", False),
            ]
        )
        journals = env["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "bank")]
        )
        if not banks:
            out["skipped"].append({"company": c.name, "reason": "NO_PARTNER_BANK"})
            continue
        bank = banks[0]
        for j in journals:
            if j.bank_account_id:
                out["skipped"].append(
                    {
                        "company": c.name,
                        "journal": j.name,
                        "reason": "ALREADY_LINKED",
                        "acc": j.bank_account_id.acc_number,
                    }
                )
                continue
            j.write({"bank_account_id": bank.id})
            out["linked"].append(
                {
                    "company": c.name,
                    "journal": j.name,
                    "acc": bank.acc_number,
                    "bank": bank.bank_id.name if bank.bank_id else "",
                }
            )
    env.cr.commit()
    Path(OUT).write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
