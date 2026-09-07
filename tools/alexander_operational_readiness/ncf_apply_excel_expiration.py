# ruff: noqa
"""Pone date_to del Excel. No toca next/auth ni la apertura.

Rangos con vencimiento ya pasado quedan expired: al facturar Odoo
debe lanzar error de NCF vencido. N/A sigue en 2099-12-31.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "/tmp")
try:
    from ncf_excel_plan import EXCEL_NCF_ROWS, plan_range
except ImportError:
    from tools.alexander_operational_readiness.ncf_excel_plan import (  # noqa: E402
        EXCEL_NCF_ROWS,
        plan_range,
    )

OUT = "/tmp/op_ready_ncf_excel_expiration.json"
QA_MIN = 99100000


def _vat(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def run(env):
    report = {"updated": [], "unchanged": [], "errors": []}
    Range = env["justech.do.ncf.range"]
    companies = {
        _vat(c.vat or c.partner_id.vat): c
        for c in env["res.company"].search([("id", "!=", 1)])
    }
    for raw in EXCEL_NCF_ROWS:
        plan = plan_range(raw)
        company = companies.get(plan["vat"])
        if not company:
            report["errors"].append({"plan": plan, "error": "COMPANY_NOT_FOUND"})
            continue
        rng = Range.search(
            [
                ("company_id", "=", company.id),
                ("prefix", "=", plan["prefix"]),
                ("sequence_start", "<", QA_MIN),
            ],
            limit=1,
        )
        if not rng:
            report["errors"].append({"plan": plan, "error": "RANGE_NOT_FOUND"})
            continue
        before = {
            "id": rng.id,
            "state": rng.state,
            "date_to": str(rng.date_to),
            "next": rng.next_ncf_display,
            "auth": rng.authorization_number,
        }
        name = f"{plan['prefix']} {company.name[:28]} auth {plan['auth']}"
        if plan["excel_expiration"]:
            name += f" (Excel vence {plan['excel_expiration']})"
        vals = {"date_to": plan["date_to"], "name": name}
        if str(rng.date_to) == plan["date_to"] and rng.name == name:
            report["unchanged"].append({**before, "prefix": plan["prefix"]})
            continue
        try:
            rng.write(vals)
            rng._recompute_operational_state()
            rec = {
                "company": company.name,
                "prefix": plan["prefix"],
                "before": before,
                "after": {
                    "state": rng.state,
                    "date_to": str(rng.date_to),
                    "next": rng.next_ncf_display,
                    "auth": rng.authorization_number,
                    "name": rng.name,
                },
                "excel_expiration": plan["excel_expiration"],
                "notes": plan["notes"],
            }
            report["updated"].append(rec)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"plan": plan, "error": str(exc), "before": before})
    env.cr.commit()
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "updated": len(report["updated"]),
                "unchanged": len(report["unchanged"]),
                "errors": report["errors"],
                "rows": [
                    {
                        "company": r["company"][:22],
                        "prefix": r["prefix"],
                        "date_to": r["after"]["date_to"],
                        "state": r["after"]["state"],
                        "excel": r["excel_expiration"],
                    }
                    for r in report["updated"]
                ],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if "env" in globals():
    run(env)
