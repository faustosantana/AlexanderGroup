# ruff: noqa
"""Verifica error de NCF vencido y que la apertura no se tocó. No consume NCF."""

import json
from pathlib import Path

from odoo.exceptions import UserError

OUT = "/tmp/op_ready_ncf_expired_error.json"
QA_MIN = 99100000
BATCH = "ALEXANDER_OPENING_2026-09-04"

EXPIRED_EXPECT = {
    ("132220112", "B11"): "2024-12-31",
    ("132271068", "B01"): "2025-12-31",
    ("132271068", "B11"): "2025-12-31",
    ("132721502", "B01"): "2025-12-31",
    ("132721502", "B11"): "2025-12-31",
    ("132710152", "B11"): "2025-12-31",
    ("132710152", "B13"): "2025-12-31",
    ("132769155", "B11"): "2025-12-31",
    ("132769155", "B13"): "2025-12-31",
}
LIVE_EXPECT = {
    ("132220112", "B15"): "2027-12-31",
    ("132220112", "B01"): "2027-12-31",
    ("133371261", "B01"): "2027-12-31",
}


def _vat(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _try_usable(rng):
    try:
        rng._check_usable()
        return {"ok": True, "error": ""}
    except UserError as exc:
        return {"ok": False, "error": str(exc)}


def run(env):
    Range = env["justech.do.ncf.range"]
    expired_checks = []
    live_checks = []
    for r in Range.search(
        [("company_id", "!=", 1), ("sequence_start", "<", QA_MIN)],
        order="company_id, prefix",
    ):
        key = (_vat(r.company_id.vat), r.prefix)
        row = {
            "company": r.company_id.name,
            "prefix": r.prefix,
            "state": r.state,
            "date_to": str(r.date_to),
            "next": r.next_ncf_display,
            "auth": r.authorization_number,
        }
        if key in EXPIRED_EXPECT:
            usable = _try_usable(rng=r)
            row.update(usable)
            row["expected_date"] = EXPIRED_EXPECT[key]
            row["date_match"] = str(r.date_to) == EXPIRED_EXPECT[key]
            row["error_says_vencido"] = "vencido" in (usable["error"] or "").lower()
            expired_checks.append(row)
        elif key in LIVE_EXPECT:
            usable = _try_usable(rng=r)
            row.update(usable)
            row["expected_date"] = LIVE_EXPECT[key]
            live_checks.append(row)

    moves = env["account.move"].search([("invoice_origin", "=", BATCH)])
    invoices = moves.filtered(lambda m: m.move_type == "out_invoice")
    ar = sum(float(m.amount_residual_signed or 0) for m in invoices)
    b150 = invoices.filtered(lambda m: m.justech_do_ncf == "B1500000150")[:1]
    r110 = env["account.move"].search(
        [
            ("justech_do_ncf", "=", "B1500000110"),
            ("company_id.vat", "ilike", "132769155"),
            ("invoice_origin", "=", BATCH),
        ],
        limit=1,
    )
    report = {
        "expired_count": len(expired_checks),
        "expired_all_block": all(
            (not x["ok"]) and x.get("error_says_vencido") and x.get("date_match")
            for x in expired_checks
        ),
        "expired_checks": expired_checks,
        "live_count": len(live_checks),
        "live_all_ok": all(x["ok"] for x in live_checks),
        "live_checks": live_checks,
        "opening": {
            "invoices": len(invoices),
            "ar": round(ar, 2),
            "b150": float(b150.amount_residual_signed or 0) if b150 else None,
            "rempart_110": float(r110.amount_residual_signed or 0) if r110 else None,
        },
        "ncf_consumed": 0,
    }
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "expired_count": report["expired_count"],
                "expired_all_block": report["expired_all_block"],
                "live_all_ok": report["live_all_ok"],
                "opening": report["opening"],
                "expired": [
                    {
                        "c": x["company"][:18],
                        "p": x["prefix"],
                        "date_to": x["date_to"],
                        "state": x["state"],
                        "vencido": x.get("error_says_vencido"),
                        "err": (x.get("error") or "")[:80],
                    }
                    for x in expired_checks
                ],
                "live": [
                    {
                        "c": x["company"][:18],
                        "p": x["prefix"],
                        "ok": x["ok"],
                        "err": x.get("error"),
                    }
                    for x in live_checks
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if "env" in globals():
    run(env)
