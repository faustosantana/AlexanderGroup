# ruff: noqa
"""Read-only NCF audit. Never consumes sequences. Never writes."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/tmp")
try:
    from authorized import (
        AUTHORIZED_B15,
        QA_MIN,
        QA_NAME_MARKERS,
        format_ncf,
        parse_b15,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from authorized import (
        AUTHORIZED_B15,
        QA_MIN,
        QA_NAME_MARKERS,
        format_ncf,
        parse_b15,
    )

OUT = os.environ.get("NCF_AUDIT_OUT", "/tmp/ncf_b15_audit.json")


def _company(env, code, spec):
    Company = env["res.company"].sudo()
    rec = Company.search([("dx_short_code", "=", code)], limit=1)
    if rec:
        return rec
    matches = Company.browse()
    for needle in spec["needles"]:
        matches |= Company.search([("name", "ilike", needle)])
    if len(matches) != 1:
        raise ValueError("COMPANY_RESOLVE_%s_%s" % (code, matches.ids))
    return matches[0]


def _official_ranges(env, company, prefix):
    Range = env["justech.do.ncf.range"].sudo()
    recs = Range.search([("company_id", "=", company.id), ("prefix", "=", prefix)])
    official = recs.filtered(
        lambda r: r.sequence_start < QA_MIN
        and not any(m.lower() in (r.name or "").lower() for m in QA_NAME_MARKERS)
    )
    return official


def _is_qa_ncf(ncf):
    text = (ncf or "").upper()
    if any(m in text for m in ("DXQA", "DX-TEST", "DX TEST", "9910")):
        return True
    parsed = parse_b15(text) if text.startswith("B15") else None
    if parsed is None and text.startswith("B15"):
        return True
    return False


def _max_real(env, company, prefix):
    numbers = []
    sources = []
    Move = env["account.move"].sudo()
    domain = [("company_id", "=", company.id)]
    fields = [
        f for f in ("justech_do_ncf", "l10n_latam_document_number") if f in Move._fields
    ]
    for rec in Move.search(domain):
        for fname in fields:
            ncf = rec[fname] or ""
            if not ncf.upper().startswith(prefix):
                continue
            if _is_qa_ncf(ncf):
                continue
            if prefix == "B15":
                num = parse_b15(ncf)
            else:
                digits = ncf[3:]
                num = int(digits) if digits.isdigit() and int(digits) < QA_MIN else None
            if num is None:
                continue
            numbers.append(num)
            sources.append((rec.id, rec.state, ncf, fname))
    if "justech.do.ncf.consumption" in env:
        Cons = env["justech.do.ncf.consumption"].sudo()
        for rec in Cons.search([("company_id", "=", company.id)]):
            ncf = rec.ncf or ""
            if not ncf.upper().startswith(prefix):
                continue
            if _is_qa_ncf(ncf):
                continue
            num = (
                rec.sequence_number
                if rec.sequence_number and rec.sequence_number < QA_MIN
                else None
            )
            if num is None and prefix == "B15":
                num = parse_b15(ncf)
            if num is None:
                continue
            numbers.append(int(num))
            sources.append((rec.id, rec.state, ncf, "consumption"))
    return (max(numbers) if numbers else None), sources


def _exists(env, company, ncf):
    Move = env["account.move"].sudo()
    domain = [
        ("company_id", "=", company.id),
        "|",
        ("justech_do_ncf", "=", ncf),
        ("l10n_latam_document_number", "=", ncf),
    ]
    moves = Move.with_context(active_test=False).search(domain)
    cons = (
        env["justech.do.ncf.consumption"]
        .sudo()
        .search([("company_id", "=", company.id), ("ncf", "=", ncf)])
        if "justech.do.ncf.consumption" in env
        else env["justech.do.ncf.consumption"].browse()
    )
    return bool(moves or cons), [(m.id, m.state, m.justech_do_ncf) for m in moves]


def snapshot_range(rng):
    last = int(rng.next_sequence) - 1 if rng.next_sequence else None
    return {
        "id": rng.id,
        "name": rng.name,
        "company": rng.company_id.name,
        "company_id": rng.company_id.id,
        "prefix": rng.prefix,
        "sequence_start": rng.sequence_start,
        "sequence_end": rng.sequence_end,
        "next_sequence": rng.next_sequence,
        "last_used": last,
        "ncf_from": format_ncf(rng.prefix, rng.sequence_start) if rng.prefix else None,
        "ncf_to": format_ncf(rng.prefix, rng.sequence_end) if rng.prefix else None,
        "ncf_next": rng.next_ncf_display,
        "ncf_last": format_ncf(rng.prefix, last) if last and last > 0 else None,
        "date_from": str(rng.date_from) if rng.date_from else None,
        "date_to": str(rng.date_to) if rng.date_to else None,
        "authorization_number": rng.authorization_number or "",
        "state": rng.state,
        "remaining_count": rng.remaining_count,
        "journal_ids": rng.journal_ids.ids,
    }


def run(env):
    report = {
        "db": env.cr.dbname,
        "companies": {},
        "blue_elite_b15": None,
        "doralex_b13": None,
    }
    for code, spec in AUTHORIZED_B15.items():
        company = _company(env, code, spec)
        ranges = _official_ranges(env, company, "B15")
        max_real, sources = _max_real(env, company, "B15")
        exists, exist_docs = _exists(env, company, spec["ncf_next"])
        row = {
            "code": code,
            "key": spec["key"],
            "company_id": company.id,
            "company": company.name,
            "ranges": [snapshot_range(r) for r in ranges],
            "MAX_REAL_B15": format_ncf("B15", max_real) if max_real else None,
            "MAX_REAL_NUM": max_real,
            "NEXT_NCF_ALREADY_EXISTS": exists,
            "next_exists_docs": exist_docs,
            "max_sources": sources[-8:],
            "authorized": {
                "from": spec["ncf_from"],
                "to": spec["ncf_to"],
                "last": spec["ncf_last"],
                "next": spec["ncf_next"],
                "date_to": str(spec["date_to"]),
                "authorization": spec["authorization_number"],
            },
        }
        report["companies"][code] = row
    blu = env["res.company"].sudo().search([("dx_short_code", "=", "BLU")], limit=1)
    if blu:
        report["blue_elite_b15"] = [
            snapshot_range(r) for r in _official_ranges(env, blu, "B15")
        ]
    dor = env["res.company"].sudo().search([("dx_short_code", "=", "DOR")], limit=1)
    if dor:
        b13 = _official_ranges(env, dor, "B13")
        max_b13, src = _max_real(env, dor, "B13")
        report["doralex_b13"] = {
            "ranges": [snapshot_range(r) for r in b13],
            "MAX_REAL_B13": format_ncf("B13", max_b13) if max_b13 else None,
            "MAX_REAL_NUM": max_b13,
            "sources": src[-8:],
        }
    fingerprint = []
    for rng in env["justech.do.ncf.range"].sudo().search([]):
        fingerprint.append(
            {
                "id": rng.id,
                "company": rng.company_id.name,
                "code": getattr(rng.company_id, "dx_short_code", ""),
                "prefix": rng.prefix,
                "start": rng.sequence_start,
                "end": rng.sequence_end,
                "next": rng.next_sequence,
                "state": rng.state,
                "auth": rng.authorization_number or "",
                "date_to": str(rng.date_to) if rng.date_to else None,
            }
        )
    report["all_ranges"] = fingerprint
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
    print("WROTE", OUT)
    for code, row in report["companies"].items():
        cur = row["ranges"][0] if row["ranges"] else {}
        print(
            "AUDIT",
            code,
            "id",
            cur.get("id"),
            "from",
            cur.get("ncf_from"),
            "to",
            cur.get("ncf_to"),
            "next",
            cur.get("ncf_next"),
            "last",
            cur.get("ncf_last"),
            "exp",
            cur.get("date_to"),
            "auth",
            cur.get("authorization_number"),
            "state",
            cur.get("state"),
            "MAX_REAL",
            row["MAX_REAL_B15"],
            "NEXT_EXISTS",
            row["NEXT_NCF_ALREADY_EXISTS"],
        )
    print("B13", report["doralex_b13"])
    print("BLU", report["blue_elite_b15"])
    return report


run(env)
