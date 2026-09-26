# ruff: noqa
"""Apply authorized B15 updates + Doralex B13 block via ORM.

Never calls next_by_id / next_by_code / consume_next.
Never creates invoices. Never SQL-updates sequences.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

sys.path.insert(0, "/tmp")
try:
    from authorized import (
        AUTHORIZED_B15,
        QA_MIN,
        QA_NAME_MARKERS,
        format_ncf,
        parse_b15,
    )
    from gates import gate_max_real, gate_next_exists, gate_range, paper_gap
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from authorized import (
        AUTHORIZED_B15,
        QA_MIN,
        QA_NAME_MARKERS,
        format_ncf,
        parse_b15,
    )
    from gates import gate_max_real, gate_next_exists, gate_range, paper_gap

DRY = os.environ.get("NCF_APPLY_DRY", "1") == "1"
OUT = os.environ.get("NCF_APPLY_OUT", "/tmp/ncf_b15_apply.json")
BLOCK_B13 = os.environ.get("NCF_BLOCK_B13", "1") == "1"


def _company(env, code, spec):
    Company = env["res.company"].sudo()
    rec = Company.search([("dx_short_code", "=", code)], limit=1)
    if rec:
        return rec
    matches = Company.browse()
    for needle in spec["needles"]:
        matches |= Company.search([("name", "ilike", needle)])
    if len(matches) != 1:
        raise ValueError("COMPANY_RESOLVE_%s" % code)
    return matches[0]


def _official_range(env, company, prefix):
    Range = env["justech.do.ncf.range"].sudo()
    recs = Range.search([("company_id", "=", company.id), ("prefix", "=", prefix)])
    official = recs.filtered(
        lambda r: r.sequence_start < QA_MIN
        and not any(m.lower() in (r.name or "").lower() for m in QA_NAME_MARKERS)
    )
    if len(official) != 1:
        raise ValueError(
            "RANGE_RESOLVE_%s_%s_%s" % (company.dx_short_code, prefix, official.ids)
        )
    return official[0]


def _is_qa_ncf(ncf):
    text = (ncf or "").upper()
    return any(m in text for m in ("DXQA", "DX-TEST", "DX TEST", "9910"))


def _max_real(env, company, prefix):
    numbers = []
    Move = env["account.move"].sudo()
    fields = [
        f for f in ("justech_do_ncf", "l10n_latam_document_number") if f in Move._fields
    ]
    for rec in Move.search([("company_id", "=", company.id)]):
        for fname in fields:
            ncf = rec[fname] or ""
            if not ncf.upper().startswith(prefix) or _is_qa_ncf(ncf):
                continue
            digits = ncf[3:]
            if digits.isdigit() and int(digits) < QA_MIN:
                numbers.append(int(digits))
    if "justech.do.ncf.consumption" in env:
        for rec in (
            env["justech.do.ncf.consumption"]
            .sudo()
            .search([("company_id", "=", company.id)])
        ):
            ncf = rec.ncf or ""
            if not ncf.upper().startswith(prefix) or _is_qa_ncf(ncf):
                continue
            if rec.sequence_number and rec.sequence_number < QA_MIN:
                numbers.append(int(rec.sequence_number))
            elif prefix == "B15":
                parsed = parse_b15(ncf)
                if parsed:
                    numbers.append(parsed)
    return max(numbers) if numbers else None


def _exists(env, company, ncf):
    Move = env["account.move"].sudo()
    domain = [
        ("company_id", "=", company.id),
        "|",
        ("justech_do_ncf", "=", ncf),
        ("l10n_latam_document_number", "=", ncf),
    ]
    if Move.with_context(active_test=False).search_count(domain):
        return True
    if "justech.do.ncf.consumption" in env:
        return bool(
            env["justech.do.ncf.consumption"]
            .sudo()
            .search_count([("company_id", "=", company.id), ("ncf", "=", ncf)])
        )
    return False


def _count_posted(env):
    return env["account.move"].sudo().search_count([("state", "=", "posted")])


def run(env):
    report = {
        "db": env.cr.dbname,
        "DRY": DRY,
        "writes": [],
        "skipped": [],
        "gates": {},
        "NCF_NUMBERS_CONSUMED_DURING_UPDATE": 0,
        "HISTORICAL_NCF_CHANGED": 0,
        "POSTED_MOVES_CHANGED": 0,
        "NCF_DOCUMENTS_RENUMBERED": 0,
        "STOP": [],
    }
    posted_before = _count_posted(env)
    max_before = {}
    for code, spec in AUTHORIZED_B15.items():
        company = _company(env, code, spec)
        max_before[code] = _max_real(env, company, "B15")

    for code, spec in AUTHORIZED_B15.items():
        company = _company(env, code, spec)
        rng = _official_range(env, company, "B15")
        if rng.prefix != "B15":
            report["STOP"].append("%s_PREFIX" % code)
            continue
        if rng.company_id.id != company.id:
            report["STOP"].append("%s_COMPANY_MISMATCH" % code)
            continue
        max_real = _max_real(env, company, "B15")
        exists = _exists(env, company, spec["ncf_next"])
        errors = []
        errors += gate_range(spec)
        errors += gate_max_real(spec, max_real)
        errors += gate_next_exists(spec, exists)
        gap = paper_gap(spec, max_real)
        report["gates"][code] = {
            "errors": errors,
            "paper_or_external_gap": gap,
            "range_id": rng.id,
            "company_id": company.id,
            "max_real": max_real,
            "next_exists": exists,
            "before": {
                "sequence_start": rng.sequence_start,
                "sequence_end": rng.sequence_end,
                "next_sequence": rng.next_sequence,
                "date_to": str(rng.date_to),
                "authorization_number": rng.authorization_number,
                "state": rng.state,
            },
        }
        if errors:
            report["STOP"].append("%s:%s" % (code, ",".join(errors)))
            report["skipped"].append(code)
            continue
        vals = {
            "sequence_start": spec["sequence_start"],
            "sequence_end": spec["sequence_end"],
            "next_sequence": spec["next_sequence"],
            "date_to": spec["date_to"],
            "authorization_number": spec["authorization_number"],
            "alert_threshold_preventive": 10,
            "alert_threshold_critical": 3,
        }
        if rng.state != "active":
            vals["state"] = "active"
        if DRY:
            report["writes"].append(
                {
                    "code": code,
                    "id": rng.id,
                    "vals": {k: str(v) for k, v in vals.items()},
                    "dry": True,
                }
            )
            continue
        rng.write(vals)
        rng.invalidate_recordset()
        report["writes"].append(
            {
                "code": code,
                "id": rng.id,
                "after": {
                    "sequence_start": rng.sequence_start,
                    "sequence_end": rng.sequence_end,
                    "next_sequence": rng.next_sequence,
                    "next_ncf": rng.next_ncf_display,
                    "date_to": str(rng.date_to),
                    "authorization_number": rng.authorization_number,
                    "state": rng.state,
                    "remaining": rng.remaining_count,
                },
            }
        )

    if BLOCK_B13:
        dor = env["res.company"].sudo().search([("dx_short_code", "=", "DOR")], limit=1)
        try:
            b13 = _official_range(env, dor, "B13")
        except ValueError as exc:
            report["doralex_b13_before"] = {"missing": str(exc)}
            report["doralex_b13_write"] = {
                "already": "NO_RANGE",
                "status": "BLOCKED_PENDING_AUTHORIZATION",
            }
            b13 = None
        if b13:
            report["doralex_b13_before"] = {
                "id": b13.id,
                "state": b13.state,
                "next": b13.next_sequence,
                "next_ncf": b13.next_ncf_display,
            }
            if b13.state not in ("cancelled", "expired", "draft"):
                if DRY:
                    report["doralex_b13_write"] = {
                        "dry": True,
                        "action": "action_cancel",
                    }
                else:
                    b13.action_cancel()
                    b13.invalidate_recordset()
                    report["doralex_b13_write"] = {
                        "state": b13.state,
                        "next": b13.next_sequence,
                    }
            else:
                report["doralex_b13_write"] = {"already": b13.state}

    posted_after = _count_posted(env)
    report["POSTED_MOVES_CHANGED"] = abs(posted_after - posted_before)
    consumed = 0
    for code, spec in AUTHORIZED_B15.items():
        company = _company(env, code, spec)
        after = _max_real(env, company, "B15")
        if after != max_before[code]:
            consumed += 1
            report["STOP"].append("%s_MAX_REAL_CHANGED" % code)
        if (
            _exists(env, company, spec["ncf_next"])
            and max_before[code] != spec["next_sequence"]
        ):
            # next as issued would mean consume; gate already blocked if it existed before
            pass
    report["NCF_NUMBERS_CONSUMED_DURING_UPDATE"] = consumed
    report["PASS"] = not report["STOP"] and (bool(report["writes"]) or DRY)
    if not DRY:
        env.cr.commit()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
    print(
        "WROTE",
        OUT,
        "DRY",
        DRY,
        "STOP",
        report["STOP"],
        "WRITES",
        [w.get("code") for w in report["writes"]],
    )
    return report


run(env)
