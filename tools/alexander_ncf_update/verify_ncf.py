# ruff: noqa
"""Post-write read-only QA. Never consumes sequences."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/tmp")
try:
    from authorized import AUTHORIZED_B15, format_ncf, remaining
    from gates import classify_balance
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from authorized import AUTHORIZED_B15, format_ncf, remaining
    from gates import classify_balance

from datetime import date

OUT = os.environ.get("NCF_VERIFY_OUT", "/tmp/ncf_b15_verify.json")


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


def _official(env, company, prefix):
    Range = env["justech.do.ncf.range"].sudo()
    recs = Range.search([("company_id", "=", company.id), ("prefix", "=", prefix)])
    official = recs.filtered(
        lambda r: r.sequence_start < 99100000
        and not any(
            m in (r.name or "").upper() for m in ("DX TEST", "DXQA", "NO FISCAL")
        )
    )
    if len(official) != 1:
        raise ValueError(
            "RANGE_RESOLVE_%s_%s_%s" % (company.dx_short_code, prefix, official.ids)
        )
    return official[0]


def run(env):
    today = date.today()
    report = {"db": env.cr.dbname, "companies": {}, "errors": []}
    for code, spec in AUTHORIZED_B15.items():
        company = _company(env, code, spec)
        rng = _official(env, company, "B15")
        last = int(rng.next_sequence) - 1
        rem = remaining(rng.sequence_end, last)
        row = {
            "COMPANY": company.name,
            "TYPE": rng.prefix,
            "RANGE_FROM": format_ncf(rng.prefix, rng.sequence_start),
            "RANGE_TO": format_ncf(rng.prefix, rng.sequence_end),
            "LAST_USED": format_ncf(rng.prefix, last),
            "NEXT": rng.next_ncf_display,
            "EXPIRATION": str(rng.date_to),
            "AUTHORIZATION": rng.authorization_number,
            "ACTIVE": rng.state == "active",
            "STATE": rng.state,
            "REMAINING": rem,
            "NATIVE_REMAINING": rng.remaining_count,
            "BALANCE": classify_balance(rem, rng.date_to, today),
        }
        report["companies"][code] = row
        if rng.sequence_start != spec["sequence_start"]:
            report["errors"].append("%s_FROM" % code)
        if rng.sequence_end != spec["sequence_end"]:
            report["errors"].append("%s_TO" % code)
        if rng.next_sequence != spec["next_sequence"]:
            report["errors"].append("%s_NEXT" % code)
        if str(rng.date_to) != str(spec["date_to"]):
            report["errors"].append("%s_DATE" % code)
        if (rng.authorization_number or "") != spec["authorization_number"]:
            report["errors"].append("%s_AUTH" % code)
        if rng.state != "active":
            report["errors"].append("%s_NOT_ACTIVE" % code)
        if rng.prefix != "B15":
            report["errors"].append("%s_PREFIX" % code)
        preview = rng.next_ncf_display
        if preview != spec["ncf_next"]:
            report["errors"].append("%s_PREVIEW" % code)
        if hasattr(rng, "dx_preview_next_ncf"):
            if rng.dx_preview_next_ncf() != spec["ncf_next"]:
                report["errors"].append("%s_DX_PREVIEW" % code)
        if rng.next_sequence != spec["next_sequence"]:
            report["errors"].append("%s_CONSUMED" % code)

    dor = env["res.company"].sudo().search([("dx_short_code", "=", "DOR")], limit=1)
    try:
        b13 = _official(env, dor, "B13")
    except ValueError:
        b13 = None
    if b13:
        report["doralex_b13"] = {
            "STATE": b13.state,
            "NEXT": b13.next_ncf_display,
            "ACTIVE": b13.state == "active",
            "STATUS": (
                "BLOCKED_PENDING_AUTHORIZATION"
                if b13.state in ("cancelled", "expired", "draft")
                else "STILL_ACTIVE"
            ),
        }
        if b13.state == "active":
            report["errors"].append("DORALEX_B13_STILL_ACTIVE")
    else:
        report["doralex_b13"] = {
            "STATE": "NO_RANGE",
            "NEXT": None,
            "ACTIVE": False,
            "STATUS": "BLOCKED_PENDING_AUTHORIZATION",
        }

    blu = env["res.company"].sudo().search([("dx_short_code", "=", "BLU")], limit=1)
    if blu:
        blu_b15 = (
            env["justech.do.ncf.range"]
            .sudo()
            .search([("company_id", "=", blu.id), ("prefix", "=", "B15")])
        )
        report["blue_elite_b15"] = [
            {
                "id": r.id,
                "state": r.state,
                "next": r.next_ncf_display,
                "end": r.sequence_end,
            }
            for r in blu_b15
        ]

    b17 = env["justech.do.ncf.range"].sudo().search([("prefix", "=", "B17")])
    report["b17_count"] = len(b17)
    if b17:
        report["errors"].append("B17_CREATED")

    report["PASS"] = not report["errors"]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
    print("WROTE", OUT, "PASS", report["PASS"], "ERRORS", report["errors"])
    for code, row in report["companies"].items():
        print(
            "QA",
            code,
            row["RANGE_FROM"],
            row["RANGE_TO"],
            row["LAST_USED"],
            row["NEXT"],
            row["EXPIRATION"],
            row["AUTHORIZATION"],
            row["ACTIVE"],
            row["REMAINING"],
            row["BALANCE"],
        )
    print("B13", report["doralex_b13"])
    return report


run(env)
