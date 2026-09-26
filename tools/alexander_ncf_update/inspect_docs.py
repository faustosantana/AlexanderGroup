# ruff: noqa
"""List every B15/B13 NCF on DOR/MAY/REM. Read-only. No consume."""

import json
import os

OUT = os.environ.get("NCF_INSPECT_OUT", "/tmp/ncf_b15_inspect.json")
TARGETS = {
    "DOR": ["B1500000151", "B1500000152", "B1300000016", "B1300000017"],
    "MAY": ["B1500000110", "B1500000111", "B1500000112", "B1500000113"],
    "REM": ["B1500000110", "B1500000111", "B1500000112"],
}


def run(env):
    report = {"db": env.cr.dbname, "companies": {}}
    Company = env["res.company"].sudo()
    Move = env["account.move"].sudo()
    for code, ncfs in TARGETS.items():
        company = Company.search([("dx_short_code", "=", code)], limit=1)
        prefix = "B15"
        moves = []
        for rec in Move.with_context(active_test=False).search(
            [("company_id", "=", company.id)]
        ):
            for fname in (
                "justech_do_ncf",
                "l10n_latam_document_number",
                "ref",
                "payment_reference",
                "name",
            ):
                if fname not in rec._fields:
                    continue
                val = rec[fname] or ""
                if not str(val).upper().startswith(("B15", "B13")):
                    continue
                moves.append(
                    {
                        "id": rec.id,
                        "state": rec.state,
                        "move_type": rec.move_type,
                        "field": fname,
                        "value": val,
                        "name": rec.name,
                    }
                )
        cons = []
        if "justech.do.ncf.consumption" in env:
            for rec in (
                env["justech.do.ncf.consumption"]
                .sudo()
                .search([("company_id", "=", company.id)])
            ):
                if (rec.ncf or "").upper().startswith(("B15", "B13")):
                    cons.append(
                        {
                            "id": rec.id,
                            "ncf": rec.ncf,
                            "seq": rec.sequence_number,
                            "state": rec.state,
                            "move_id": rec.move_id.id if rec.move_id else None,
                        }
                    )
        hits = {}
        for ncf in ncfs:
            found = [m for m in moves if str(m["value"]).upper() == ncf]
            found_c = [c for c in cons if (c["ncf"] or "").upper() == ncf]
            hits[ncf] = {
                "moves": found,
                "consumptions": found_c,
                "exists": bool(found or found_c),
            }
        b15_nums = sorted(
            {
                int(str(m["value"])[3:])
                for m in moves
                if str(m["value"]).upper().startswith("B15")
                and str(m["value"])[3:].isdigit()
            }
        )
        report["companies"][code] = {
            "company": company.name,
            "company_id": company.id,
            "b15_moves": [
                m for m in moves if str(m["value"]).upper().startswith("B15")
            ],
            "b15_numbers": b15_nums,
            "b15_max": max(b15_nums) if b15_nums else None,
            "consumptions": cons,
            "target_hits": hits,
        }
        print(
            "INSPECT",
            code,
            "b15_nums",
            b15_nums,
            "max",
            max(b15_nums) if b15_nums else None,
            "hits",
            {k: v["exists"] for k, v in hits.items()},
        )
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
    print("WROTE", OUT)
    return report


run(env)
