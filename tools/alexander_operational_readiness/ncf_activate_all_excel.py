# ruff: noqa
"""Activa los 34 rangos de la planilla Pendientes. No toca lote de apertura."""

import json
from pathlib import Path

import sys

sys.path.insert(0, "/tmp")
try:
    from ncf_excel_plan import EXCEL_NCF_ROWS, plan_range
except ImportError:
    from tools.alexander_operational_readiness.ncf_excel_plan import (  # noqa: E402
        EXCEL_NCF_ROWS,
        plan_range,
    )

OUT = "/tmp/op_ready_ncf_all_excel.json"
QA_MIN = 99100000
PURCHASE = {"B11", "B13", "B17"}


def _vat(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _hist_max(env, company, prefix):
    moves = env["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("justech_do_ncf", "=like", f"{prefix}%"),
            ("state", "=", "posted"),
            (
                "move_type",
                "in",
                ("out_invoice", "out_refund", "in_invoice", "in_refund"),
            ),
        ]
    )
    best = None
    for m in moves:
        n = m.justech_do_ncf or ""
        if len(n) == 11 and n[:3] == prefix and n[3:].isdigit():
            seq = int(n[3:])
            if seq < QA_MIN and (best is None or seq > best):
                best = seq
    return best


def run(env):
    report = {"applied": [], "errors": [], "active_after": []}
    Range = env["justech.do.ncf.range"]
    Doc = env["justech.do.fiscal.document.type"]
    companies = {
        _vat(c.vat or c.partner_id.vat): c
        for c in env["res.company"].search([("id", "!=", 1)])
    }
    for raw in EXCEL_NCF_ROWS:
        company = companies.get(plan_range(raw)["vat"])
        hist = _hist_max(env, company, raw["declared_type"]) if company else None
        plan = plan_range(raw, max_historical_seq=hist)
        rec = {"plan": plan}
        if not company:
            rec["error"] = "COMPANY_NOT_FOUND"
            report["errors"].append(rec)
            continue
        doc = Doc.search([("prefix", "=", plan["prefix"])], limit=1)
        if not doc:
            rec["error"] = "DOC_TYPE_NOT_FOUND"
            report["errors"].append(rec)
            continue
        existing = Range.search(
            [
                ("company_id", "=", company.id),
                ("document_type_id", "=", doc.id),
                ("sequence_start", "<", QA_MIN),
            ],
            limit=1,
        )
        jtype = "purchase" if plan["prefix"] in PURCHASE else "sale"
        journal = env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", jtype)], limit=1
        )
        name = f"{plan['prefix']} {company.name[:28]} auth {plan['auth']}"
        if plan["excel_expiration"] and plan["date_to"] == "2099-12-31":
            name += f" (Excel vence {plan['excel_expiration']})"
        vals = {
            "name": name,
            "company_id": company.id,
            "document_type_id": doc.id,
            "authorization_number": plan["auth"],
            "sequence_start": plan["start"],
            "sequence_end": plan["end"],
            "next_sequence": plan["next"],
            "date_from": plan["date_from"],
            "date_to": plan["date_to"],
        }
        if journal:
            vals["journal_ids"] = [(6, 0, journal.ids)]
        try:
            if existing:
                if existing.state in ("cancelled", "expired", "depleted", "active"):
                    if existing.state != "draft":
                        existing.action_set_draft()
                keep_next = max(plan["next"], existing.next_sequence or 0)
                if existing.next_sequence and existing.next_sequence > plan["next"]:
                    plan["notes"].append(
                        f"PRESERVED_EXISTING_NEXT {existing.next_sequence}"
                    )
                vals["next_sequence"] = keep_next
                if keep_next > vals["sequence_end"]:
                    vals["sequence_end"] = keep_next
                existing.write({k: v for k, v in vals.items() if k != "company_id"})
                if existing.state == "draft":
                    existing.action_activate()
                if existing.state != "active":
                    existing.write({"date_to": "2099-12-31", "state": "active"})
                    existing._recompute_operational_state()
                    if existing.state != "active":
                        existing.sudo().write({"date_to": "2099-12-31"})
                        Range.browse(existing.id).sudo().write({"state": "active"})
                rng = existing
            else:
                rng = Range.create(vals)
                rng.action_activate()
                if rng.state != "active":
                    rng.write({"date_to": "2099-12-31", "state": "draft"})
                    rng.action_activate()
            rec.update(
                {
                    "id": rng.id,
                    "state": rng.state,
                    "next": rng.next_ncf_display,
                    "from": rng.sequence_start,
                    "to": rng.sequence_end,
                    "date_to": str(rng.date_to),
                    "auth": rng.authorization_number,
                    "notes": plan["notes"],
                }
            )
            report["applied"].append(rec)
        except Exception as exc:  # noqa: BLE001
            rec["error"] = str(exc)
            report["errors"].append(rec)
    env.cr.commit()
    for r in Range.search(
        [
            ("company_id", "!=", 1),
            ("sequence_start", "<", QA_MIN),
        ],
        order="company_id, prefix",
    ):
        report["active_after"].append(
            {
                "company": r.company_id.name,
                "prefix": r.prefix,
                "state": r.state,
                "from": r.sequence_start,
                "to": r.sequence_end,
                "next": r.next_ncf_display,
                "auth": r.authorization_number,
                "date_to": str(r.date_to),
            }
        )
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "applied": len(report["applied"]),
                "errors": report["errors"],
                "active_after": report["active_after"],
                "states": {
                    s: sum(1 for a in report["active_after"] if a["state"] == s)
                    for s in sorted({a["state"] for a in report["active_after"]})
                },
            },
            indent=2,
            default=str,
        )
    )


if "env" in globals():
    run(env)
