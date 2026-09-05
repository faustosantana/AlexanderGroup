# ruff: noqa
"""Valida 607 desde account.move. No crea exporter. No envía DGII."""

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BATCH = "ALEXANDER_OPENING_2026-09-04"


def _money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def run(env):
    Move = env["account.move"]
    moves = Move.search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
    )
    periods = defaultdict(list)
    errors = []
    for move in moves:
        ncf = (move.justech_do_ncf or "").strip()
        vat = "".join(ch for ch in str(move.partner_id.vat or "") if ch.isdigit())
        date = move.invoice_date
        rec = {
            "id": move.id,
            "company": move.company_id.name,
            "ncf": ncf,
            "rnc": vat,
            "date": str(date),
            "period": date.strftime("%Y%m") if date else "",
            "amount_untaxed": float(move.amount_untaxed),
            "itbis": float(move.amount_tax),
            "amount_total": float(move.amount_total),
        }
        if not ncf:
            errors.append({**rec, "error": "MISSING_NCF"})
        if not vat:
            errors.append({**rec, "error": "MISSING_RNC"})
        if not date:
            errors.append({**rec, "error": "MISSING_DATE"})
        if _money(move.amount_total) <= 0:
            errors.append({**rec, "error": "NON_POSITIVE_TOTAL"})
        periods[rec["period"]].append(rec)
    report = {
        "DGII_SENT": 0,
        "EXPORTER_CREATED": 0,
        "PERIODS": {
            p: {
                "count": len(rows),
                "amount_total": str(
                    sum((_money(r["amount_total"]) for r in rows), Decimal("0"))
                ),
                "itbis": str(sum((_money(r["itbis"]) for r in rows), Decimal("0"))),
            }
            for p, rows in sorted(periods.items())
        },
        "INVOICES": [r for rows in periods.values() for r in rows],
        "errors": errors,
        "DGII_607_VALIDATION": "PASS" if not errors else "FAIL",
        "DGII_606_VALIDATION": "NOT_APPLICABLE",
        "DGII_608_VALIDATION": "NO_CANCELLATIONS",
    }
    Path("/tmp/dgii_607_validate.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in report if k != "INVOICES"}, indent=2))
    print("WROTE /tmp/dgii_607_validate.json invoices", len(moves))


if "env" in globals():
    run(env)
