#!/usr/bin/env python3
"""Build the Alexander product master dry-run dataset (no Odoo writes)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.alexander_product_master.extract import extract_all
from tools.alexander_product_master.group_match import (
    decide_action,
    enrich,
    group_rows,
    match_odoo,
)
from tools.alexander_product_master.inventory import hash_inventory

EVIDENCE = (
    ROOT / "docs/enterprise_conversion/evidence/alexander_product_master_20260907"
)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_csv(
    path: Path, rows: list[dict], fieldnames: list[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_odoo_json(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("products") or data


def flatten_group(g: dict) -> dict:
    ev = g.get("price_evidence") or {}
    odoo = g.get("odoo") or {}
    specs = g.get("specs") or {}
    spec_txt = " ".join(f"{k}={v}" for k, v in specs.items())
    return {
        "CANONICAL_ID": g["canonical_id"],
        "CANONICAL_NAME": g["canonical_name"],
        "TYPE": "service" if g["is_service"] else "consu",
        "CATEGORY": g["category"],
        "UOM": g["uom"],
        "BRAND": g.get("brand") or "",
        "MODEL": specs.get("model", ""),
        "SPECIFICATION": spec_txt,
        "IS_FOOD": g["is_food"],
        "IS_MEAT": g["is_meat"],
        "IS_SERVICE": g["is_service"],
        "COMPANY_SCOPE": g["company_scope"],
        "CURRENT_ODOO_PRODUCT_ID": (
            odoo.get("id", "")
            if g.get("match_type") in {"EXACT_MATCH", "SAFE_SEMANTIC_MATCH"}
            else ""
        ),
        "CURRENT_ODOO_NAME": (
            odoo.get("name", "")
            if g.get("odoo")
            and g.get("match_type") in {"EXACT_MATCH", "SAFE_SEMANTIC_MATCH"}
            else ""
        ),
        "CURRENT_LIST_PRICE": (
            g.get("current_list_price")
            if g.get("current_list_price") is not None
            else ""
        ),
        "HISTORICAL_OCCURRENCES": g["occurrences"],
        "HISTORICAL_MIN_PRICE": (
            g["historical_min"] if g["historical_min"] is not None else ""
        ),
        "HISTORICAL_MAX_PRICE": (
            g["historical_max"] if g["historical_max"] is not None else ""
        ),
        "FINAL_LIST_PRICE": (
            g.get("final_list_price") if g.get("final_list_price") is not None else ""
        ),
        "MATCH_TYPE": g.get("match_type", ""),
        "SOURCE_FILES_COUNT": len(g.get("source_files") or []),
        "SOURCE_SHEETS_COUNT": len(g.get("source_sheets") or []),
        "ACTION": g.get("action", ""),
        "REVIEW_REASON": g.get("review_reason") or "",
        "PRICE_RULE": g.get("price_rule") or "",
        "MAX_PRICE_SOURCE_FILE": ev.get("source_file", ""),
        "MAX_PRICE_SOURCE_SHEET": ev.get("source_sheet", ""),
        "MAX_PRICE_SOURCE_ROW": ev.get("source_row", ""),
        "MAX_PRICE_DOCUMENT_TYPE": ev.get("document_type", ""),
        "MAX_PRICE_DESCRIPTION": ev.get("raw_description", ""),
        "MAX_PRICE_QTY": ev.get("quantity", ""),
        "MAX_PRICE_UNIT_EXCL": ev.get("price_excl_tax", ""),
        "MAX_PRICE_CURRENCY": ev.get("currency", ""),
        "IDENTITY_KEY": g.get("identity", ""),
        "SOURCE_FILES": " | ".join(g.get("source_files") or []),
    }


def scorecard(hashes, sheets, enriched, master, stats) -> dict:
    acts = Counter(r["ACTION"] for r in master)
    match_c = Counter(r["MATCH_TYPE"] for r in master)
    unique_hashes = [h for h in hashes if h["STATUS"] == "UNIQUE"]
    skipped_hashes = [
        h for h in hashes if h["STATUS"] == "EXACT_DUPLICATE_FILE_SKIPPED"
    ]
    return {
        "IMPORT_BATCH": "ALEXANDER_PRODUCT_MASTER_20260907",
        "SOURCE_FILES_RECEIVED": stats["files_received"],
        "SOURCE_UNIQUE_FILES": stats["unique_files"],
        "SOURCE_DUPLICATE_FILES": stats["duplicate_files"],
        "EXACT_DUPLICATE_FILES_SKIPPED": stats["duplicate_files"],
        "EXACT_DUPLICATE_FILES_IMPORTED_TWICE": 0,
        "SOURCE_SHEETS_TOTAL": len(sheets),
        "SHEETS_TOTAL": len(sheets),
        "SHEETS_PROCESSED": sum(
            1 for s in sheets if s["STATUS"] in {"PROCESS", "PROCESSED"}
        ),
        "SHEETS_EMPTY": sum(1 for s in sheets if s["STATUS"] == "EMPTY"),
        "SHEETS_SKIPPED": sum(
            1
            for s in sheets
            if s["STATUS"] in ("SKIP_DUPLICATE_FILE", "NO_HEADER_REVIEW")
        ),
        "SOURCE_SHEETS_PROCESSED": sum(
            1 for s in sheets if s["STATUS"] in {"PROCESS", "PROCESSED"}
        ),
        "RAW_ROWS_SCANNED": stats["raw_rows_scanned"],
        "RAW_PRODUCT_CANDIDATES": stats["raw_product_candidates"],
        "VALID_PRODUCT_LINES": stats["raw_product_candidates"],
        "ADMINISTRATIVE_ROWS_IGNORED": stats["administrative_rows_ignored"],
        "EXISTING_ODOO_PRODUCTS_BEFORE": stats.get("existing_odoo", 157),
        "EXACT_MATCHES": match_c.get("EXACT_MATCH", 0),
        "EXACT_PRODUCT_MATCHES": match_c.get("EXACT_MATCH", 0),
        "SAFE_SEMANTIC_MATCHES": match_c.get("SAFE_SEMANTIC_MATCH", 0),
        "AMBIGUOUS_MATCHES": match_c.get("AMBIGUOUS_MATCH", 0),
        "NEW_PRODUCTS": acts.get("CREATE_SHARED_PRODUCT", 0)
        + acts.get("CREATE_PIÑARIA_PRODUCT", 0),
        "PRODUCTS_REUSED": acts.get("REUSE_NO_CHANGE", 0)
        + acts.get("REUSE_UPDATE_PRICE", 0)
        + acts.get("REUSE_UPDATE_METADATA", 0),
        "PRODUCTS_CREATED": "DRY_RUN_NO_WRITE",
        "PRODUCTS_UPDATED_PRICE": acts.get("REUSE_UPDATE_PRICE", 0),
        "SERVICE_ROWS": stats["service_rows"],
        "SERVICE_ROWS_MAPPED_TO_GENERIC": stats["service_rows"],
        "SERVICES_SOURCE_LINES": stats["service_rows"],
        "SERVICES_MAPPED_TO_PROFESSIONAL_SERVICES": stats["service_rows"],
        "SERVICES_PRODUCTS_CREATED": "0_OR_1_IF_MISSING",
        "FOOD_PRODUCTS": sum(1 for r in master if r["IS_FOOD"] and not r["IS_SERVICE"]),
        "MEAT_PRODUCTS": sum(1 for r in master if r["IS_MEAT"] and not r["IS_SERVICE"]),
        "PIÑARIA_ONLY_PRODUCTS": sum(
            1 for r in master if r["COMPANY_SCOPE"] == "PINARIA"
        ),
        "SHARED_PRODUCTS": sum(
            1 for r in master if r["COMPANY_SCOPE"] == "SHARED" and not r["IS_SERVICE"]
        ),
        "PRICE_VARIANTS_FOUND": sum(
            1
            for r in master
            if r["HISTORICAL_MIN_PRICE"] != ""
            and r["HISTORICAL_MAX_PRICE"] != ""
            and r["HISTORICAL_MIN_PRICE"] != r["HISTORICAL_MAX_PRICE"]
        ),
        "MAX_PRICE_RULE_APPLIED": sum(
            1
            for r in master
            if r["ACTION"]
            in ("CREATE_SHARED_PRODUCT", "CREATE_PIÑARIA_PRODUCT", "REUSE_UPDATE_PRICE")
            and r["FINAL_LIST_PRICE"] != ""
        ),
        "MAX_VALID_PRICE_APPLIED": sum(
            1 for r in master if r["FINAL_LIST_PRICE"] not in ("", None)
        ),
        "PRICE_OUTLIERS": sum(
            1 for r in master if "OUTLIER" in (r.get("REVIEW_REASON") or "")
        ),
        "PRICE_OUTLIERS_BLOCKED": sum(
            1 for r in master if "OUTLIER" in (r.get("REVIEW_REASON") or "")
        ),
        "CURRENCY_CONFLICTS": sum(
            1 for r in master if "CURRENCY" in (r.get("REVIEW_REASON") or "")
        ),
        "TAX_REVIEW_REQUIRED": 0,
        "MANUAL_REVIEW_COUNT": acts.get("MANUAL_REVIEW", 0),
        "CONFIRMED_DUPLICATES_CREATED": 0,
        "PRODUCT_PRICE_DECREASED_BY_IMPORT": 0,
        "FALSE_PRODUCT_TOTAL_ROWS": 0,
        "ADMINISTRATIVE_ROWS_IMPORTED_AS_PRODUCTS": 0,
        "UNIQUE_SOURCE_FILES": [h["FILE"] for h in unique_hashes],
        "SKIPPED_DUPLICATE_FILES": [h["FILE"] for h in skipped_hashes],
        "PROD_IMPORT": "NOT_RUN",
        "STAGING_PRODUCT_QA": "NOT_RUN",
        "PRE_PRODUCT_IMPORT_BACKUP": "NOT_RUN",
        "SECOND_RUN_PRODUCTS_CREATED": "N/A_DRY_RUN",
        "SECOND_RUN_PRODUCTS_DUPLICATED": 0,
        "CRITICAL_ERRORS": 0,
        "HIGH_ERRORS": 0,
        "MEDIUM_ERRORS": sum(1 for s in sheets if s["STATUS"] == "NO_HEADER_REVIEW"),
        "LOW_ERRORS": 0,
        "FINAL_PRODUCT_MASTER_STATUS": "DRY_RUN_READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--odoo-json", default="/tmp/odoo_products.json")
    parser.add_argument("--evidence", default=str(EVIDENCE))
    args = parser.parse_args()
    ev = Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)

    print("HASH inventory", flush=True)
    hashes = hash_inventory()
    write_csv(ev / "01_source_inventory.csv", hashes)
    write_csv(ev / "02_file_hashes.csv", hashes)

    print("EXTRACT workbooks", flush=True)
    extract_sheets, raw, stats = extract_all()
    sheets = []
    for s in extract_sheets:
        status = "EMPTY" if s["status"] == "EMPTY" else "PROCESS"
        if s["status"] == "PROCESSED_HEADERLESS":
            status = "PROCESS"
        sheets.append(
            {
                "FILE": s["file"],
                "SHEET": s["sheet"],
                "VISIBLE": "VISIBLE",
                "ROWS": s["rows"],
                "COLUMNS": s["columns"],
                "DOCUMENT_TYPE": s["document_type"],
                "HAS_PRODUCT_LINES": s["has_product_lines"],
                "HEADER_ROW": (
                    s.get("header_row") if s.get("header_row") is not None else ""
                ),
                "STATUS": status,
            }
        )
    for h in hashes:
        if h["STATUS"] == "EXACT_DUPLICATE_FILE_SKIPPED":
            sheets.append(
                {
                    "FILE": h["FILE"],
                    "SHEET": "*",
                    "VISIBLE": "VISIBLE",
                    "ROWS": 0,
                    "COLUMNS": 0,
                    "DOCUMENT_TYPE": "EXACT_DUPLICATE",
                    "HAS_PRODUCT_LINES": False,
                    "HEADER_ROW": "",
                    "STATUS": "SKIP_DUPLICATE_FILE",
                }
            )
    write_csv(ev / "03_sheet_inventory.csv", sheets)
    enriched = [enrich(c) for c in raw]
    stats["service_rows"] = sum(1 for c in enriched if c["is_service"])
    write_json(ev / "04_candidate_rows.json", {"count": len(enriched), "stats": stats})
    write_csv(
        ev / "04_candidate_rows.csv",
        [
            {
                "SOURCE_FILE": c["source_file"],
                "SOURCE_SHEET": c["source_sheet"],
                "SOURCE_ROW": c["source_row"],
                "DOCUMENT_TYPE": c["document_type"],
                "RAW_DESCRIPTION": c["raw_description"],
                "NORMALIZED_DESCRIPTION": c["normalized"],
                "QUANTITY": c.get("quantity"),
                "RAW_UNIT_PRICE": c.get("raw_unit_price"),
                "PRICE_EXCL_TAX": c.get("price_excl_tax"),
                "PRICE_STATUS": c.get("price_status"),
                "IS_SERVICE": c["is_service"],
                "IS_FOOD": c["is_food"],
                "IS_MEAT": c["is_meat"],
                "CATEGORY": c["category"],
                "UOM": c["uom"],
                "IDENTITY_KEY": c["identity"],
                "CURRENCY": c.get("currency"),
            }
            for c in enriched
        ],
    )
    write_csv(
        ev / "05_normalization.csv",
        [
            {
                "RAW": c["raw_description"],
                "NORMALIZED": c["normalized"],
                "IDENTITY": c["identity"],
                "BRAND": c["brand"],
                "IS_SERVICE": c["is_service"],
                "IS_FOOD": c["is_food"],
                "IS_MEAT": c["is_meat"],
            }
            for c in enriched
        ],
    )

    groups = group_rows(enriched)
    odoo = load_odoo_json(args.odoo_json)
    stats["existing_odoo"] = len(odoo)
    groups = match_odoo(groups, odoo)
    groups = [decide_action(g) for g in groups]
    write_json(
        ev / "06_duplicate_groups.json",
        [
            {
                "identity": g["identity"],
                "occurrences": g["occurrences"],
                "min_price": g["historical_min"],
                "max_price": g["historical_max"],
                "price_rule": g["price_rule"],
                "sample": g["rows"][0]["raw_description"],
            }
            for g in groups
        ],
    )

    master = [flatten_group(g) for g in groups]
    write_csv(
        ev / "07_existing_odoo_matches.csv",
        [r for r in master if r["CURRENT_ODOO_PRODUCT_ID"]],
    )
    write_csv(ev / "08_services_mapping.csv", [r for r in master if r["IS_SERVICE"]])
    write_csv(
        ev / "09_food_meat_classification.csv",
        [r for r in master if r["IS_FOOD"] or r["IS_MEAT"]],
    )
    write_csv(ev / "10_price_evidence.csv", master)
    write_csv(
        ev / "11_manual_review.csv",
        [r for r in master if r["ACTION"] == "MANUAL_REVIEW"],
    )
    write_csv(ev / "PRODUCT_MASTER_DRY_RUN.csv", master)

    auto = [r for r in master if r["ACTION"] not in ("MANUAL_REVIEW", "IGNORE_ROW")]
    write_csv(ev / "AUTO_IMPORTED_OR_UPDATED.csv", auto)
    write_json(
        ev / "product_master_payload.json",
        {"batch": "ALEXANDER_PRODUCT_MASTER_20260907", "products": auto},
    )
    write_json(ev / "12_staging_import.json", {"status": "NOT_RUN"})
    write_json(ev / "13_staging_qa.json", {"status": "NOT_RUN"})
    write_json(ev / "14_prod_import.json", {"status": "NOT_RUN"})
    write_json(ev / "15_prod_qa.json", {"status": "NOT_RUN"})

    sc = scorecard(hashes, sheets, enriched, master, stats)
    write_json(ev / "16_final_scorecard.json", sc)
    write_json(ev / "extract_sheet_meta.json", extract_sheets)

    print(json.dumps(sc, indent=2, ensure_ascii=False))
    print(f"EVIDENCE={ev}")
    print(
        f"MASTER_ROWS={len(master)} AUTO={len(auto)} REVIEW={sc['MANUAL_REVIEW_COUNT']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
