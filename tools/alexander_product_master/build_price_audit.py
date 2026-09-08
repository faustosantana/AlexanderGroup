"""Build PRODUCT_PRICE_AUDIT.csv and PRICE_REVIEW_REQUIRED.csv from a dump."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .price_classify import classify_price

AUDIT_COLUMNS = [
    "product_tmpl_id",
    "product_id",
    "name",
    "active",
    "company_id",
    "type",
    "sale_ok",
    "purchase_ok",
    "list_price",
    "standard_price",
    "currency",
    "uom",
    "category",
    "last_quotation_price",
    "last_quotation_date",
    "last_sale_order_price",
    "last_sale_order_date",
    "last_invoice_price",
    "last_invoice_date",
    "recent_avg_price",
    "price_status",
    "price_difference_pct",
    "recommended_action",
    "evidence",
    "notes",
]

REVIEW_STATUSES = {
    "ZERO_PRICE",
    "SUSPICIOUS_LOW",
    "SUSPICIOUS_HIGH",
    "HISTORICAL_PRICE_DIFFERENCE",
    "MANUAL_REVIEW",
    "PRICE_LIST_DEPENDENT",
}


def enrich(row: dict) -> dict:
    classified = classify_price(row)
    out = {k: row.get(k, "") for k in AUDIT_COLUMNS}
    out.update(classified)
    out["active"] = bool(row.get("active"))
    out["sale_ok"] = bool(row.get("sale_ok"))
    out["purchase_ok"] = bool(row.get("purchase_ok"))
    return out


def review_sort_key(row: dict):
    recent = (
        1
        if any(
            row.get(k)
            for k in (
                "last_quotation_date",
                "last_sale_order_date",
                "last_invoice_date",
            )
        )
        else 0
    )
    diff = abs(row.get("price_difference_pct") or 0)
    zero = 1 if row.get("price_status") == "ZERO_PRICE" else 0
    return (
        0 if row.get("active") and row.get("sale_ok") else 1,
        0 if recent else 1,
        -diff,
        0 if zero else 1,
        row.get("name") or "",
    )


def summarize(rows: list[dict]) -> dict:
    status = Counter(r["price_status"] for r in rows)
    return {
        "BASELINE_PRODUCTS": 1601,
        "PRODUCTS_AUDITED": len(rows),
        "PRODUCTS_WITH_SALE_PRICE": sum(
            1 for r in rows if float(r.get("list_price") or 0) > 0.005
        ),
        "PRODUCTS_WITH_ZERO_PRICE": sum(
            1 for r in rows if abs(float(r.get("list_price") or 0)) < 0.005
        ),
        "PRODUCTS_WITH_RECENT_QUOTATION": sum(
            1 for r in rows if r.get("last_quotation_price") not in (None, "")
        ),
        "PRODUCTS_WITH_RECENT_SALE": sum(
            1 for r in rows if r.get("last_sale_order_price") not in (None, "")
        ),
        "PRODUCTS_WITH_RECENT_INVOICE": sum(
            1 for r in rows if r.get("last_invoice_price") not in (None, "")
        ),
        "PRICE_OK": status.get("PRICE_OK", 0),
        "ZERO_PRICE": status.get("ZERO_PRICE", 0),
        "SUSPICIOUS_LOW": status.get("SUSPICIOUS_LOW", 0),
        "SUSPICIOUS_HIGH": status.get("SUSPICIOUS_HIGH", 0),
        "NO_SALES_HISTORY": status.get("NO_SALES_HISTORY", 0),
        "HISTORICAL_PRICE_DIFFERENCE": status.get("HISTORICAL_PRICE_DIFFERENCE", 0),
        "PRICE_LIST_DEPENDENT": status.get("PRICE_LIST_DEPENDENT", 0),
        "MANUAL_REVIEW": status.get("MANUAL_REVIEW", 0),
        "REVIEW_REQUIRED": sum(1 for r in rows if r["price_status"] in REVIEW_STATUSES),
        "PRICES_AUTOMATICALLY_CHANGED": 0,
        "STANDARD_PRICE_CHANGED": 0,
        "HISTORICAL_DOCUMENTS_CHANGED": 0,
        "NCF_CHANGED": 0,
        "STOCK_MOVES_CREATED": 0,
        "STOCK_QUANTS_CREATED": 0,
    }


def build(dump_path: Path, out_dir: Path) -> dict:
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    rows = [enrich(p) for p in payload["products"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = out_dir / "PRODUCT_PRICE_AUDIT.csv"
    review = out_dir / "PRICE_REVIEW_REQUIRED.csv"
    with audit.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    review_rows = sorted(
        [r for r in rows if r["price_status"] in REVIEW_STATUSES],
        key=review_sort_key,
    )
    with review.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(review_rows)
    stats = summarize(rows)
    (out_dir / "00_price_audit_summary.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.dump, args.out_dir), ensure_ascii=False, indent=2))
