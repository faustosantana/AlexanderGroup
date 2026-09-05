# ruff: noqa
"""Configura solo secuencias NCF SAFE_TO_ACTIVATE. No usa rangos QA 9910xxxx."""

import json
import os
from pathlib import Path

PAYLOAD_PATH = os.environ.get("OPENING_PAYLOAD_JSON", "/tmp/opening_payload.json")
DRY = os.environ.get("OPENING_DRY_RUN", "0") == "1"
QA_START = 99100000


def _vat(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


COMPANY_VAT = {
    "INVERSIONES DORALEX,S.RL.": "132220112",
    "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.": "132271068",
    "DOMINION BUSINESS,S.R.L.": "132721502",
    "INVERSIONES EL MAYUMA, S.R.L.": "132710152",
    "REMPART GROUP S.R.L.": "132769155",
    "BLUE ELITE, S.R.L.": "133371261",
}


def find_company(env, name):
    vat = COMPANY_VAT.get(name)
    Company = env["res.company"]
    if vat:
        for c in Company.search([("id", "!=", 1)]):
            if _vat(c.vat) == vat or _vat(c.partner_id.vat) == vat:
                return c
    rec = Company.search([("name", "=", name)], limit=1)
    return rec


def ncf_seq(ncf):
    n = str(ncf or "")
    if len(n) == 11 and n[3:].isdigit():
        return int(n[3:])
    return None


def apply_one(env, row):
    out = dict(row)
    out["applied"] = False
    company = find_company(env, row["company"])
    if not company:
        out["apply_error"] = "COMPANY_NOT_FOUND"
        return out
    if not row.get("activate"):
        out["apply_error"] = "NOT_SAFE"
        return out
    Doc = env["justech.do.fiscal.document.type"]
    doc = Doc.search([("prefix", "=", row["ncf_type"])], limit=1)
    if not doc:
        out["apply_error"] = "DOC_TYPE_NOT_FOUND"
        return out
    Range = env["justech.do.ncf.range"]
    start = ncf_seq(row["declared_range_start"])
    end = ncf_seq(row["declared_range_end"])
    nxt = ncf_seq(row["calculated_next"])
    if None in (start, end, nxt):
        out["apply_error"] = "MISSING_SEQ_BOUNDS"
        return out
    exp = row.get("expiration")
    if not exp or str(exp).upper() in ("N/A", "NA", "NO APLICA"):
        out["apply_error"] = "MISSING_EXPIRATION"
        return out
    # cancel QA ranges of same company+type so they cannot consume 9910
    qa = Range.search(
        [
            ("company_id", "=", company.id),
            ("document_type_id", "=", doc.id),
            ("sequence_start", ">=", QA_START),
            ("state", "=", "active"),
        ]
    )
    if qa and not DRY:
        qa.action_cancel()
        out["qa_cancelled"] = qa.ids
    existing = Range.search(
        [
            ("company_id", "=", company.id),
            ("document_type_id", "=", doc.id),
            ("sequence_start", "<", QA_START),
        ],
        limit=1,
    )
    name = f"ALEXANDER REAL {row['ncf_type']} {company.name[:20]}"
    vals = {
        "name": name,
        "company_id": company.id,
        "document_type_id": doc.id,
        "authorization_number": row.get("authorization") or False,
        "sequence_start": start,
        "sequence_end": end,
        "next_sequence": nxt,
        "date_from": "2026-01-01",
        "date_to": exp,
    }
    journal = env["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
    )
    if DRY:
        out["applied"] = True
        out["dry"] = vals
        return out
    if existing:
        if existing.sequence_start != start or existing.sequence_end != end:
            out["apply_error"] = (
                f"RANGE_BOUNDS_MISMATCH existing={existing.sequence_start}-"
                f"{existing.sequence_end} declared={start}-{end}"
            )
            return out
        write_vals = {"next_sequence": nxt}
        if journal and not existing.journal_ids:
            write_vals["journal_ids"] = [(6, 0, journal.ids)]
        if existing.state == "draft":
            existing.write({**vals, **write_vals})
            existing.action_activate()
        elif existing.state == "cancelled":
            existing.action_set_draft()
            existing.write({**vals, **write_vals})
            existing.action_activate()
        elif existing.state == "active":
            existing.write(write_vals)
        else:
            out["apply_error"] = f"EXISTING_NOT_ACTIVABLE:{existing.state}"
            return out
        out["range_id"] = existing.id
        out["applied"] = True
        out["next"] = existing.next_ncf_display
        return out
    create_vals = dict(vals)
    if journal:
        create_vals["journal_ids"] = [(6, 0, journal.ids)]
    rec = Range.create(create_vals)
    rec.action_activate()
    out["range_id"] = rec.id
    out["applied"] = True
    out["next"] = rec.next_ncf_display
    return out


def cancel_remaining_qa(env, report):
    """Cierra rangos QA 9910xxxx activos. No son autorización DGII."""
    Range = env["justech.do.ncf.range"]
    qa = Range.search(
        [
            ("sequence_start", ">=", QA_START),
            ("state", "=", "active"),
            ("company_id", "!=", 1),
        ]
    )
    report["qa_ranges_found_active"] = [
        {
            "id": r.id,
            "company": r.company_id.name,
            "prefix": r.prefix,
            "start": r.sequence_start,
            "end": r.sequence_end,
            "next": r.next_sequence,
        }
        for r in qa
    ]
    if qa and not DRY:
        qa.with_context(
            mail_create_nosubscribe=True,
            mail_notrack=True,
            tracking_disable=True,
        ).action_cancel()
    report["QA_RANGES_CANCELLED"] = qa.ids if not DRY else []
    report["QA_RANGES_WOULD_CANCEL"] = qa.ids


def run(env):
    payload = json.loads(Path(PAYLOAD_PATH).read_text(encoding="utf-8"))
    report = {
        "corrected": [],
        "blocked": [],
        "NCF_SEQUENCE_CORRECTED": 0,
        "NCF_SEQUENCE_BLOCKED": 0,
    }
    for row in payload.get("ncf_sequences", []):
        if row.get("activate"):
            rec = apply_one(env, row)
            if rec.get("applied"):
                report["corrected"].append(rec)
                report["NCF_SEQUENCE_CORRECTED"] += 1
            else:
                report["blocked"].append(rec)
                report["NCF_SEQUENCE_BLOCKED"] += 1
        else:
            report["blocked"].append(row)
            report["NCF_SEQUENCE_BLOCKED"] += 1
    cancel_remaining_qa(env, report)
    Path("/tmp/ncf_apply_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
