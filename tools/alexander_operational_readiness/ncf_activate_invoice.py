# ruff: noqa
"""Activa solo NCF de facturación enviados y seguros para PIN/DOM/BLU.

No inventa rangos. No toca Doralex B15/B01 ni Mayuma/Rempart B15.
Blue Elite B15 queda bloqueado (last/next fuera del rango 1-20).
"""

import json
from pathlib import Path

OUT = "/tmp/op_ready_ncf_activate.json"

# Datos literales de Plantilla_PENDIENTES 02_Secuencias_NCF
ACTIVATE = [
    {
        "company_vat": "132271068",
        "prefix": "B15",
        "start": 93,
        "end": 103,
        "next": 93,
        "auth": "6005464536",
        "date_to": "2028-01-01",
        "reason": "planilla next=B1500000093 = inicio de rango; last 092 bajo rango (mismo patrón Doralex B01)",
    },
    {
        "company_vat": "132721502",
        "prefix": "B15",
        "start": 140,
        "end": 163,
        "next": 145,
        "auth": "5004909756",
        "date_to": "2026-12-31",
        "reason": "planilla CONSISTENT last=144 next=145 rango 140-163",
    },
    {
        "company_vat": "133371261",
        "prefix": "B01",
        "start": 1,
        "end": 15,
        "next": 1,
        "auth": "6005109961",
        "date_to": "2027-12-31",
        "reason": "planilla CONSISTENT; B15 Blue Elite conflicted (101/102 > 1-20) no se activa",
    },
]


def _vat(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def run(env):
    report = {"applied": [], "skipped": [], "safe_after": []}
    Range = env["justech.do.ncf.range"]
    Doc = env["justech.do.fiscal.document.type"]
    for row in ACTIVATE:
        company = False
        for c in env["res.company"].search([("id", "!=", 1)]):
            if _vat(c.vat or c.partner_id.vat) == row["company_vat"]:
                company = c
                break
        if not company:
            report["skipped"].append({**row, "error": "COMPANY_NOT_FOUND"})
            continue
        doc = Doc.search([("prefix", "=", row["prefix"])], limit=1)
        if not doc:
            report["skipped"].append({**row, "error": "DOC_TYPE_NOT_FOUND"})
            continue
        existing = Range.search(
            [
                ("company_id", "=", company.id),
                ("document_type_id", "=", doc.id),
                ("sequence_start", "<", 99100000),
            ],
            limit=1,
        )
        journal = env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
        )
        vals = {
            "name": f"ALEXANDER REAL {row['prefix']} {company.name[:24]}",
            "company_id": company.id,
            "document_type_id": doc.id,
            "authorization_number": row["auth"],
            "sequence_start": row["start"],
            "sequence_end": row["end"],
            "next_sequence": row["next"],
            "date_from": "2026-01-01",
            "date_to": row["date_to"],
        }
        if journal:
            vals["journal_ids"] = [(6, 0, journal.ids)]
        if existing:
            if (
                existing.sequence_start != row["start"]
                or existing.sequence_end != row["end"]
            ):
                report["skipped"].append(
                    {
                        **row,
                        "company": company.name,
                        "error": f"BOUNDS_MISMATCH {existing.sequence_start}-{existing.sequence_end}",
                    }
                )
                continue
            if existing.state == "cancelled":
                existing.action_set_draft()
            existing.write({k: v for k, v in vals.items() if k != "company_id"})
            if existing.state != "active":
                existing.action_activate()
            rec = existing
        else:
            rec = Range.create(vals)
            rec.action_activate()
        report["applied"].append(
            {
                "company": company.name,
                "prefix": rec.prefix,
                "from": rec.sequence_start,
                "to": rec.sequence_end,
                "next": rec.next_ncf_display,
                "state": rec.state,
                "auth": rec.authorization_number,
                "reason": row["reason"],
                "id": rec.id,
            }
        )
    env.cr.commit()
    for r in Range.search([("company_id", "!=", 1), ("state", "=", "active")]):
        report["safe_after"].append(
            {
                "company": r.company_id.name,
                "prefix": r.prefix,
                "next": r.next_ncf_display,
                "from": r.sequence_start,
                "to": r.sequence_end,
                "auth": r.authorization_number,
            }
        )
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
