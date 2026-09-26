#!/usr/bin/env python3
"""Classify product.template dump into PRODUCT_TYPE_FINAL_AUDIT.csv.

Read-only. Never writes to Odoo.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from alexander_product_master.type_nature import classify_nature  # noqa: E402

DUMP = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/golive_templates.json")
OUT_DIR = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else ROOT
    / "docs/enterprise_conversion/evidence/ALEXANDER_GROUP_GO_LIVE_BASELINE_20260926"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)
rows_in = json.loads(DUMP.read_text(encoding="utf-8"))

fields = [
    "PRODUCT_ID",
    "NAME",
    "CURRENT_TYPE",
    "PROPOSED_TYPE",
    "CURRENT_SALE_OK",
    "PROPOSED_SALE_OK",
    "CURRENT_PURCHASE_OK",
    "PROPOSED_PURCHASE_OK",
    "COMPANY",
    "CATEGORY",
    "EVIDENCE",
    "CONFIDENCE",
    "ACTION",
    "REASON",
]
out_rows = []
summary = {
    "AUDITED": 0,
    "PHYSICAL_AS_SERVICE_FOUND": 0,
    "PHYSICAL_AS_SERVICE_WRITABLE": 0,
    "SERVICE_AS_PHYSICAL_FOUND": 0,
    "SERVICE_AS_PHYSICAL_WRITABLE": 0,
    "AMBIGUOUS": 0,
    "KEEP": 0,
    "KEEP_ARCHIVED": 0,
    "MANUAL_REVIEW": 0,
    "WRITABLE": 0,
    "ACTIONS": {},
    "WRITABLE_ROWS": [],
    "AMBIGUOUS_ROWS": [],
    "PHYSICAL_AS_SERVICE_ROWS": [],
}
for rec in rows_in:
    name = rec.get("name") or rec.get("NAME") or ""
    current = rec.get("type") or rec.get("CURRENT_TYPE") or ""
    sale_ok = bool(
        rec.get("sale_ok") if "sale_ok" in rec else rec.get("CURRENT_SALE_OK")
    )
    purchase_ok = bool(
        rec.get("purchase_ok")
        if "purchase_ok" in rec
        else rec.get("CURRENT_PURCHASE_OK")
    )
    active = bool(rec.get("active", rec.get("ACTIVE", True)))
    company = (
        rec.get("company_name")
        or rec.get("COMPANY")
        or ("SHARED" if not rec.get("company") else str(rec.get("company")))
    )
    if rec.get("company") in (0, None, False) and not rec.get("company_name"):
        company = "SHARED"
    categ = rec.get("categ") or rec.get("CATEGORY") or ""
    nature = classify_nature(
        name,
        current_type=current,
        category=categ,
        active=active,
        sale_ok=sale_ok,
        purchase_ok=purchase_ok,
    )
    pid = rec.get("id") or rec.get("PRODUCT_ID")
    row = {
        "PRODUCT_ID": pid,
        "NAME": name,
        "CURRENT_TYPE": current,
        "PROPOSED_TYPE": nature["PROPOSED_TYPE"],
        "CURRENT_SALE_OK": sale_ok,
        "PROPOSED_SALE_OK": nature["PROPOSED_SALE_OK"],
        "CURRENT_PURCHASE_OK": purchase_ok,
        "PROPOSED_PURCHASE_OK": nature["PROPOSED_PURCHASE_OK"],
        "COMPANY": company,
        "CATEGORY": categ,
        "EVIDENCE": nature["MISMATCH"] or nature["NATURE"],
        "CONFIDENCE": nature["CONFIDENCE"],
        "ACTION": nature["ACTION"],
        "REASON": nature["REASON"],
    }
    out_rows.append(row)
    summary["AUDITED"] += 1
    summary["ACTIONS"][nature["ACTION"]] = (
        summary["ACTIONS"].get(nature["ACTION"], 0) + 1
    )
    if nature["MISMATCH"] == "PHYSICAL_AS_SERVICE":
        summary["PHYSICAL_AS_SERVICE_FOUND"] += 1
        summary["PHYSICAL_AS_SERVICE_ROWS"].append(row)
        if nature["WRITABLE"]:
            summary["PHYSICAL_AS_SERVICE_WRITABLE"] += 1
    if nature["MISMATCH"] == "SERVICE_AS_PHYSICAL":
        summary["SERVICE_AS_PHYSICAL_FOUND"] += 1
        if nature["WRITABLE"]:
            summary["SERVICE_AS_PHYSICAL_WRITABLE"] += 1
    if nature["ACTION"] == "MANUAL_REVIEW":
        summary["AMBIGUOUS"] += 1
        summary["AMBIGUOUS_ROWS"].append(row)
    if nature["ACTION"] == "KEEP":
        summary["KEEP"] += 1
    if nature["ACTION"] == "KEEP_ARCHIVED":
        summary["KEEP_ARCHIVED"] += 1
    if nature["WRITABLE"]:
        summary["WRITABLE"] += 1
        summary["WRITABLE_ROWS"].append(row)

csv_path = OUT_DIR / "PRODUCT_TYPE_FINAL_AUDIT.csv"
with csv_path.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    writer.writerows(out_rows)
(OUT_DIR / "05_product_types_dry_run.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
print("WROTE", csv_path, "rows", len(out_rows))
print(
    json.dumps(
        {
            k: v
            for k, v in summary.items()
            if k != "WRITABLE_ROWS"
            and k != "AMBIGUOUS_ROWS"
            and k != "PHYSICAL_AS_SERVICE_ROWS"
        },
        ensure_ascii=False,
        indent=2,
    )
)
if summary["WRITABLE_ROWS"]:
    print("WRITABLE")
    for row in summary["WRITABLE_ROWS"]:
        print(row)
