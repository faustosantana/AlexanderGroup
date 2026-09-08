"""Build dry-run CSV + apply payload from a catalog dump. No Odoo writes."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .type_nature import classify_nature

DRY_COLUMNS = [
    "PRODUCT_ID",
    "TEMPLATE_ID",
    "NAME",
    "CURRENT_TYPE",
    "PROPOSED_TYPE",
    "CURRENT_SALE_OK",
    "PROPOSED_SALE_OK",
    "CURRENT_PURCHASE_OK",
    "PROPOSED_PURCHASE_OK",
    "CATEGORY",
    "COMPANY",
    "ACTIVE",
    "EVIDENCE",
    "CONFIDENCE",
    "ACTION",
    "REASON",
    "MISMATCH",
    "SALE_LINE_REFERENCES",
    "PURCHASE_LINE_REFERENCES",
    "INVOICE_LINE_REFERENCES",
    "STOCK_MOVE_REFERENCES",
    "STOCK_QUANT_REFERENCES",
    "VALUATION_LAYER_REFERENCES",
    "IS_STORABLE",
    "STANDARD_PRICE",
    "LIST_PRICE",
]


def classify_row(row: dict) -> dict:
    nature = classify_nature(
        row["NAME"],
        current_type=row.get("TYPE") or "",
        category=row.get("CATEGORY") or "",
        active=bool(row.get("ACTIVE", True)),
        sale_ok=bool(row.get("SALE_OK", True)),
        purchase_ok=bool(row.get("PURCHASE_OK", True)),
    )
    evidence = []
    if row.get("INVOICE_LINE_REFERENCES"):
        evidence.append(f"invoice_lines={row['INVOICE_LINE_REFERENCES']}")
    if row.get("CATEGORY"):
        evidence.append(f"category={row['CATEGORY']}")
    if row.get("COMPANY"):
        evidence.append(f"company={row['COMPANY']}")
    evidence.append(f"normalized={nature['NORMALIZED']}")
    out = {
        "PRODUCT_ID": row.get("PRODUCT_ID"),
        "TEMPLATE_ID": row.get("TEMPLATE_ID"),
        "NAME": row.get("NAME"),
        "CURRENT_TYPE": row.get("TYPE"),
        "PROPOSED_TYPE": nature["PROPOSED_TYPE"],
        "CURRENT_SALE_OK": bool(row.get("SALE_OK")),
        "PROPOSED_SALE_OK": nature["PROPOSED_SALE_OK"],
        "CURRENT_PURCHASE_OK": bool(row.get("PURCHASE_OK")),
        "PROPOSED_PURCHASE_OK": nature["PROPOSED_PURCHASE_OK"],
        "CATEGORY": row.get("CATEGORY") or "",
        "COMPANY": row.get("COMPANY") or "",
        "ACTIVE": bool(row.get("ACTIVE", True)),
        "EVIDENCE": "; ".join(evidence),
        "CONFIDENCE": nature["CONFIDENCE"],
        "ACTION": nature["ACTION"],
        "REASON": nature["REASON"],
        "MISMATCH": nature["MISMATCH"],
        "SALE_LINE_REFERENCES": row.get("SALE_LINE_REFERENCES", 0),
        "PURCHASE_LINE_REFERENCES": row.get("PURCHASE_LINE_REFERENCES", 0),
        "INVOICE_LINE_REFERENCES": row.get("INVOICE_LINE_REFERENCES", 0),
        "STOCK_MOVE_REFERENCES": row.get("STOCK_MOVE_REFERENCES", 0),
        "STOCK_QUANT_REFERENCES": row.get("STOCK_QUANT_REFERENCES", 0),
        "VALUATION_LAYER_REFERENCES": row.get("VALUATION_LAYER_REFERENCES", 0),
        "IS_STORABLE": bool(row.get("IS_STORABLE")),
        "STANDARD_PRICE": row.get("STANDARD_PRICE", 0),
        "LIST_PRICE": row.get("LIST_PRICE", 0),
        "WRITABLE": nature["WRITABLE"],
        "NATURE": nature["NATURE"],
    }
    if out["IS_STORABLE"] and out["ACTION"].startswith("FIX"):
        out["ACTION"] = "MANUAL_REVIEW"
        out["WRITABLE"] = False
        out["REASON"] += "; storable — inventory policy out of scope"
        out["CONFIDENCE"] = "AMBIGUOUS"
    if int(out.get("STOCK_QUANT_REFERENCES") or 0) or int(
        out.get("VALUATION_LAYER_REFERENCES") or 0
    ):
        if out["ACTION"].startswith("FIX_TYPE"):
            out["ACTION"] = "MANUAL_REVIEW"
            out["WRITABLE"] = False
            out["REASON"] += "; has stock/valuation — skip type change"
            out["CONFIDENCE"] = "AMBIGUOUS"
    return out


def summarize(rows: list[dict]) -> dict:
    writable = [r for r in rows if r["WRITABLE"]]
    return {
        "PRODUCTS_AUDITED": len(rows),
        "PHYSICAL_AS_SERVICE_FOUND": sum(
            1 for r in rows if r["MISMATCH"] == "PHYSICAL_AS_SERVICE"
        ),
        "PHYSICAL_AS_SERVICE_WRITABLE": sum(
            1 for r in writable if r["MISMATCH"] == "PHYSICAL_AS_SERVICE"
        ),
        "SERVICE_AS_PHYSICAL_FOUND": sum(
            1 for r in rows if r["MISMATCH"] == "SERVICE_AS_PHYSICAL"
        ),
        "PHYSICAL_PURCHASE_OK_FALSE_FOUND": sum(
            1
            for r in rows
            if r["NATURE"] == "PHYSICAL_GOOD"
            and not r["CURRENT_PURCHASE_OK"]
            and r["ACTIVE"]
        ),
        "PHYSICAL_PURCHASE_OK_WRITABLE": sum(
            1
            for r in writable
            if r["NATURE"] == "PHYSICAL_GOOD" and not r["CURRENT_PURCHASE_OK"]
        ),
        "ACTIONS": dict(Counter(r["ACTION"] for r in rows)),
        "WRITABLE_COUNT": len(writable),
        "AMBIGUOUS_PRODUCT_TYPES": [
            {"TEMPLATE_ID": r["TEMPLATE_ID"], "NAME": r["NAME"], "REASON": r["REASON"]}
            for r in rows
            if r["CONFIDENCE"] == "AMBIGUOUS" or r["ACTION"] == "MANUAL_REVIEW"
        ],
        "WRITABLE_TYPE_FIXES": [
            {
                "TEMPLATE_ID": r["TEMPLATE_ID"],
                "NAME": r["NAME"],
                "CURRENT_TYPE": r["CURRENT_TYPE"],
                "PROPOSED_TYPE": r["PROPOSED_TYPE"],
                "ACTION": r["ACTION"],
            }
            for r in writable
            if r["CURRENT_TYPE"] != r["PROPOSED_TYPE"]
        ],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DRY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(dump_path: Path, out_dir: Path) -> dict:
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    classified = [classify_row(r) for r in payload["products"]]
    stats = summarize(classified)
    stats["PRODUCT_TYPE_FIELDS"] = payload.get("PRODUCT_TYPE_FIELDS")
    stats["CURRENT_GOODS_IMPLEMENTATION"] = payload.get("CURRENT_GOODS_IMPLEMENTATION")
    stats["CURRENT_SERVICE_IMPLEMENTATION"] = payload.get(
        "CURRENT_SERVICE_IMPLEMENTATION"
    )
    write_csv(out_dir / "PRODUCT_TYPE_AUDIT_DRY_RUN.csv", classified)
    write_csv(
        out_dir / "PRODUCT_TYPE_AUDIT_WRITABLE.csv",
        [r for r in classified if r["WRITABLE"]],
    )
    apply_rows = [
        {
            "NAME": r["NAME"],
            "TEMPLATE_ID": r["TEMPLATE_ID"],
            "PRODUCT_ID": r["PRODUCT_ID"],
            "CURRENT_TYPE": r["CURRENT_TYPE"],
            "PROPOSED_TYPE": r["PROPOSED_TYPE"],
            "PROPOSED_SALE_OK": r["PROPOSED_SALE_OK"],
            "PROPOSED_PURCHASE_OK": r["PROPOSED_PURCHASE_OK"],
            "PROPOSED_IS_STORABLE": False,
            "ACTION": r["ACTION"],
            "CONFIDENCE": r["CONFIDENCE"],
            "STANDARD_PRICE": r["STANDARD_PRICE"],
        }
        for r in classified
        if r["WRITABLE"]
    ]
    (out_dir / "product_type_apply_payload.json").write_text(
        json.dumps({"rows": apply_rows, "stats": stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "00_dry_run_summary.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.dump, args.out_dir), ensure_ascii=False, indent=2))
