#!/usr/bin/env python3
"""Phase 2 dry-run: 2-decimal prices + rematch of manual review. No Excel rescan."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.alexander_product_master.classify import (  # noqa: E402
    extract_brand,
    extract_specs,
    identity_key,
    is_food,
    is_meat,
    is_service,
)
from tools.alexander_product_master.money import (
    has_excess_precision,
    money2,
    money2_float,
)
from tools.alexander_product_master.prices import pick_max_price
from tools.alexander_product_master.textutil import collapse, is_admin_text

EV1 = ROOT / "docs/enterprise_conversion/evidence/alexander_product_master_20260907"
EV2 = (
    ROOT
    / "docs/enterprise_conversion/evidence/alexander_product_master_phase2_20260908"
)

VALID_PRICE_STATUS = {
    "EXCL_HINT",
    "FROM_SUBTOTAL",
    "RECONCILED_SUBTOTAL",
    "RECONCILED_TOTAL_TAX",
    "RECONCILED_TOTAL_NO_TAX",
    "RECONCILED_ITBIS",
    "RECONCILED_ITBIS_INCL",
    "ASSUMED_EXCL_QTY1",
    "ASSUMED_EXCL",
}

NON_PRODUCT_EXACT = {
    "preliminares",
    "pisos",
    "artista",
    "direccion tecnica",
    "construccion acera",
}

INVOICE_CODE_RE = __import__("re").compile(
    r"^fact[-_]?b\d{2}[-_]?\d+", __import__("re").I
)


def _f(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_catalog(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("products") or data


def index_catalog(products: list[dict]) -> dict:
    by_norm = defaultdict(list)
    by_ident = defaultdict(list)
    for p in products:
        by_norm[collapse(p["name"])].append(p)
        by_ident[identity_key(p["name"])].append(p)
    return {"by_norm": by_norm, "by_ident": by_ident, "all": products}


def match_existing(name: str, idx: dict) -> tuple[str, dict | None]:
    n = collapse(name)
    exact = idx["by_norm"].get(n) or []
    if len(exact) == 1:
        return "MATCH_EXISTING_EXACT", exact[0]
    if len(exact) > 1:
        return "LIKELY_EXISTING_REVIEW", None
    ident = identity_key(name)
    same = idx["by_ident"].get(ident) or []
    if len(same) == 1:
        return "MATCH_EXISTING_SAFE", same[0]
    if len(same) > 1:
        return "LIKELY_EXISTING_REVIEW", None
    return "NEW_PRODUCT_WITHOUT_PRICE", None


def is_non_product(name: str) -> bool:
    n = collapse(name)
    if is_admin_text(name):
        return True
    if n in NON_PRODUCT_EXACT:
        return True
    if INVOICE_CODE_RE.match(n or ""):
        return True
    if n.startswith("fact-b"):
        return True
    return False


def load_candidates(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def prices_for_identity(cands: list[dict], ident: str, name: str) -> list[dict]:
    out = []
    n = collapse(name)
    for c in cands:
        if c.get("DOCUMENT_TYPE") == "COST_ANALYSIS":
            continue
        if (
            c.get("IDENTITY_KEY") != ident
            and collapse(c.get("RAW_DESCRIPTION") or "") != n
        ):
            continue
        if c.get("PRICE_STATUS") not in VALID_PRICE_STATUS:
            continue
        price = _f(c.get("PRICE_EXCL_TAX"))
        if not price or price <= 0:
            continue
        out.append(c)
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fields or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def classify_review(row: dict, idx: dict, cands: list[dict]) -> dict:
    name = row.get("CANONICAL_NAME") or ""
    reasons = [p for p in (row.get("REVIEW_REASON") or "").split(";") if p]
    ident = row.get("IDENTITY_KEY") or identity_key(name)
    match_type, matched = match_existing(name, idx)
    valid_rows = prices_for_identity(cands, ident, name)
    prices = [_f(c["PRICE_EXCL_TAX"]) for c in valid_rows]
    max_price, price_rule = pick_max_price([p for p in prices if p])
    evidence = None
    if max_price and valid_rows:
        evidence = max(valid_rows, key=lambda c: _f(c["PRICE_EXCL_TAX"]) or 0)

    food = _truthy(row.get("IS_FOOD")) or is_food(name)
    meat = _truthy(row.get("IS_MEAT")) or is_meat(name)
    service = _truthy(row.get("IS_SERVICE")) or is_service(name)
    if collapse(name) in {"transporte", "direccion tecnica", "preliminares"}:
        service = True

    current = None
    if matched:
        current = float(matched.get("list_price") or 0)

    proposed = None
    if max_price:
        proposed = money2_float(
            max(max_price, current or 0) if current is not None else max_price
        )
    elif current is not None:
        proposed = money2_float(current)

    new_class = match_type
    action = "KEEP_MANUAL_REVIEW"
    confidence = "LOW"

    if is_non_product(name) and not matched:
        new_class = "NON_PRODUCT"
        action = "IGNORE_NON_PRODUCT"
        confidence = "HIGH"
    elif service:
        new_class = "SERVICE"
        action = "MAP_TO_SERVICES"
        proposed = 0.0
        confidence = "HIGH"
        if matched and collapse(matched["name"]) not in {
            "servicios profesionales",
            "servicio profesional",
        }:
            # existing physical product named like a service — do not overwrite
            action = "KEEP_MANUAL_REVIEW"
            new_class = "LIKELY_EXISTING_REVIEW"
            confidence = "MEDIUM"
    elif matched:
        new_class = match_type
        if max_price and current is not None and money2(max_price) > money2(current):
            action = "RESOLVE_EXISTING_UPDATE_PRICE"
            proposed = money2_float(max(max_price, current))
            confidence = "HIGH" if match_type == "MATCH_EXISTING_EXACT" else "MEDIUM"
        else:
            action = "RESOLVE_EXISTING_NO_CHANGE"
            proposed = money2_float(current) if current is not None else None
            confidence = "HIGH" if match_type == "MATCH_EXISTING_EXACT" else "MEDIUM"
    elif match_type == "LIKELY_EXISTING_REVIEW":
        action = "KEEP_MANUAL_REVIEW"
        new_class = "LIKELY_EXISTING_REVIEW"
        confidence = "MEDIUM"
    elif (food or meat) and max_price and price_rule != "PRICE_OUTLIER_REVIEW":
        new_class = "NEW_PRODUCT_WITH_PRICE"
        action = "CREATE_PIÑARIA_PRODUCT"
        proposed = money2_float(max_price)
        confidence = "HIGH"
    elif max_price and price_rule == "PRICE_OUTLIER_REVIEW":
        new_class = "PRICE_OUTLIER_UNRESOLVED"
        action = "KEEP_MANUAL_REVIEW"
        confidence = "LOW"
    elif max_price:
        # Valid price found for a new shared item — do not auto-create shared.
        new_class = "NEW_PRODUCT_WITH_PRICE_NEEDS_APPROVAL"
        action = "KEEP_MANUAL_REVIEW"
        proposed = money2_float(max_price)
        confidence = "MEDIUM"
    else:
        new_class = "NEW_PRODUCT_WITHOUT_PRICE"
        action = "KEEP_MANUAL_REVIEW"
        confidence = "HIGH"

    return {
        "REVIEW_ID": row.get("CANONICAL_ID"),
        "RAW_DESCRIPTION": name,
        "ORIGINAL_REASON": row.get("REVIEW_REASON") or "",
        "NEW_CLASSIFICATION": new_class,
        "MATCHED_PRODUCT_ID": matched["id"] if matched else "",
        "MATCHED_PRODUCT": matched["name"] if matched else "",
        "VALID_PRICE_FOUND": max_price if max_price is not None else "",
        "CURRENT_LIST_PRICE": current if current is not None else "",
        "PROPOSED_LIST_PRICE": proposed if proposed is not None else "",
        "PROPOSED_LIST_PRICE_2_DECIMALS": (
            f"{money2(proposed):.2f}" if proposed is not None else ""
        ),
        "ACTION": action,
        "CONFIDENCE": confidence,
        "SOURCE": row.get("SOURCE_FILES") or "",
        "IS_FOOD": food,
        "IS_MEAT": meat,
        "IS_SERVICE": service,
        "PRICE_RULE": price_rule,
        "PRICE_EVIDENCE_FILE": (evidence or {}).get("SOURCE_FILE", ""),
        "PRICE_EVIDENCE_SHEET": (evidence or {}).get("SOURCE_SHEET", ""),
        "PRICE_EVIDENCE_ROW": (evidence or {}).get("SOURCE_ROW", ""),
        "IDENTITY_KEY": ident,
        "ORIGINAL_REASONS": "|".join(reasons),
    }


def precision_rows(products: list[dict]) -> list[dict]:
    rows = []
    for p in products:
        price = float(p.get("list_price") or 0)
        if not has_excess_precision(price):
            continue
        fixed = money2_float(price)
        rows.append(
            {
                "REVIEW_ID": f"PREC-{p['id']}",
                "RAW_DESCRIPTION": p["name"],
                "ORIGINAL_REASON": "EXCESS_LIST_PRICE_PRECISION",
                "NEW_CLASSIFICATION": "PRICE_PRECISION_FIX",
                "MATCHED_PRODUCT_ID": p["id"],
                "MATCHED_PRODUCT": p["name"],
                "VALID_PRICE_FOUND": "",
                "CURRENT_LIST_PRICE": price,
                "PROPOSED_LIST_PRICE": fixed,
                "PROPOSED_LIST_PRICE_2_DECIMALS": f"{money2(fixed):.2f}",
                "ACTION": "PRICE_PRECISION_FIX",
                "CONFIDENCE": "HIGH",
                "SOURCE": "odoo_catalog",
                "IS_FOOD": is_food(p["name"]),
                "IS_MEAT": is_meat(p["name"]),
                "IS_SERVICE": collapse(p["name"]) == "servicios profesionales",
                "PRICE_RULE": "ROUND_HALF_UP_2",
                "PRICE_EVIDENCE_FILE": "",
                "PRICE_EVIDENCE_SHEET": "",
                "PRICE_EVIDENCE_ROW": "",
                "IDENTITY_KEY": identity_key(p["name"]),
                "ORIGINAL_REASONS": "EXCESS_PRECISION",
            }
        )
    return rows


def duplicate_audit(products: list[dict]) -> list[dict]:
    by_norm = defaultdict(list)
    by_ident = defaultdict(list)
    for p in products:
        by_norm[collapse(p["name"])].append(p)
        specs = extract_specs(p["name"])
        brand = extract_brand(p["name"])
        key = "|".join(
            [
                collapse(p["name"]),
                brand,
                specs.get("model", ""),
                specs.get("size", ""),
                specs.get("caliber", ""),
                p.get("uom") or "",
            ]
        )
        by_ident[identity_key(p["name"])].append(p)
    out = []
    seen = set()
    for key, items in by_ident.items():
        if len(items) < 2:
            continue
        names = {collapse(i["name"]) for i in items}
        kind = "CONFIRMED_SAME_PRODUCT" if len(names) == 1 else "POSSIBLE_DUPLICATE"
        spec_keys = {tuple(sorted(extract_specs(i["name"]).items())) for i in items}
        num_sets = {tuple(re.findall(r"\d+(?:\.\d+)?", i["name"])) for i in items}
        if len(spec_keys) > 1 or len(num_sets) > 1:
            if kind != "CONFIRMED_SAME_PRODUCT":
                kind = "DISTINCT_VARIANT"
        if kind == "DISTINCT_VARIANT":
            continue
        ids = tuple(sorted(i["id"] for i in items))
        if ids in seen:
            continue
        seen.add(ids)
        out.append(
            {
                "KIND": kind,
                "IDENTITY": key,
                "IDS": ",".join(str(i["id"]) for i in items),
                "NAMES": " | ".join(i["name"] for i in items),
                "PRICES": " | ".join(str(i["list_price"]) for i in items),
            }
        )
    return out


def name_issues(products: list[dict]) -> list[dict]:
    rows = []
    for p in products:
        name = p["name"] or ""
        issues = []
        if "  " in name or "\n" in name or name != name.strip():
            issues.append("WHITESPACE")
        if is_admin_text(name) or collapse(name) in {"total", "subtotal", "itbis"}:
            issues.append("ADMIN_NAME")
        if "\ufffd" in name:
            issues.append("BROKEN_CHAR")
        if issues:
            rows.append({"id": p["id"], "name": name, "issues": "|".join(issues)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-json", default="/tmp/phase2_prod_catalog.json")
    parser.add_argument("--evidence1", default=str(EV1))
    parser.add_argument("--evidence2", default=str(EV2))
    args = parser.parse_args()
    ev1 = Path(args.evidence1)
    ev2 = Path(args.evidence2)
    ev2.mkdir(parents=True, exist_ok=True)

    catalog_raw = json.loads(Path(args.catalog_json).read_text(encoding="utf-8"))
    products = catalog_raw.get("products") or []
    idx = index_catalog(products)
    review = list(csv.DictReader((ev1 / "11_manual_review.csv").open(encoding="utf-8")))
    cands = load_candidates(ev1 / "04_candidate_rows.csv")
    food_src = list(
        csv.DictReader((ev1 / "09_food_meat_classification.csv").open(encoding="utf-8"))
    )

    reason_counts = Counter()
    for r in review:
        for part in (r.get("REVIEW_REASON") or "").split(";"):
            if part:
                reason_counts[part] += 1

    classified = [classify_review(r, idx, cands) for r in review]
    prec = precision_rows(products)
    dry = prec + classified
    write_csv(ev2 / "PHASE2_PRODUCT_REVIEW_DRY_RUN.csv", dry)

    acts = Counter(r["ACTION"] for r in classified)
    classes = Counter(r["NEW_CLASSIFICATION"] for r in classified)

    dups = duplicate_audit(products)
    write_csv(ev2 / "26_post_import_duplicates.csv", dups)
    names = name_issues(products)
    write_csv(ev2 / "25_name_issues.csv", names)

    food_matrix = []
    for r in food_src:
        name = r["CANONICAL_NAME"]
        mt, matched = match_existing(name, idx)
        food_matrix.append(
            {
                "DESCRIPTION": name,
                "FOOD": r.get("IS_FOOD"),
                "MEAT": r.get("IS_MEAT"),
                "EXISTING_PRODUCT": matched["name"] if matched else "",
                "EXISTING_ID": matched["id"] if matched else "",
                "VALID_PRICE": r.get("HISTORICAL_MAX_PRICE")
                or r.get("FINAL_LIST_PRICE")
                or "",
                "CREATED": r.get("ACTION", "").startswith("CREATE"),
                "REVIEW_REASON": r.get("REVIEW_REASON") or r.get("ACTION"),
                "PHASE2_MATCH": mt,
            }
        )
    write_csv(ev2 / "24_food_meat_matrix.csv", food_matrix)

    pinaria = [p for p in products if p.get("company_id")]
    shared = [p for p in products if not p.get("company_id")]
    svc = [p for p in products if collapse(p["name"]) == "servicios profesionales"]

    outliers = [
        r for r in classified if "PRICE_OUTLIER" in (r["ORIGINAL_REASON"] or "")
    ]
    write_csv(ev2 / "17_outlier_review.csv", outliers)
    ambig_col = [
        r
        for r in classified
        if "PRICE_COLUMN_AMBIGUOUS" in (r["ORIGINAL_REASON"] or "")
    ]
    write_csv(ev2 / "19_ambiguous_column.csv", ambig_col)
    ambig_match = [
        r for r in classified if "AMBIGUOUS_MATCH" in (r["ORIGINAL_REASON"] or "")
    ]
    write_csv(ev2 / "20_ambiguous_match.csv", ambig_match)

    apply_rows = [r for r in dry if r["ACTION"] not in {"KEEP_MANUAL_REVIEW"}]
    (ev2 / "phase2_apply_payload.json").write_text(
        json.dumps(
            {"batch": "ALEXANDER_PRODUCT_PHASE2_20260908", "rows": apply_rows},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    remaining = [r for r in classified if r["ACTION"] == "KEEP_MANUAL_REVIEW"]
    missing_rem = [
        r
        for r in remaining
        if "MISSING_VALID_PRICE" in r["ORIGINAL_REASON"]
        and r["NEW_CLASSIFICATION"] == "NEW_PRODUCT_WITHOUT_PRICE"
    ]
    score = {
        "BASELINE_PRODUCTS": len(products),
        "PRODUCT_PRICE_DECIMAL_POLICY": 2,
        "ODOO_PRODUCT_PRICE_DIGITS": next(
            (
                p["digits"]
                for p in catalog_raw.get("decimal_precision", [])
                if p["name"] == "Product Price"
            ),
            None,
        ),
        "PRICE_EXCESS_PRECISION_FOUND": len(prec),
        "PRICE_EXCESS_PRECISION_FIXED": "DRY_RUN",
        "PRODUCT_PRICES_STILL_ABOVE_2_DECIMALS": "DRY_RUN",
        "MANUAL_REVIEW_BEFORE": len(review),
        "REASON_COUNTS_BEFORE": dict(reason_counts),
        "MANUAL_REVIEW_RESOLVED_EXISTING": acts.get("RESOLVE_EXISTING_NO_CHANGE", 0)
        + acts.get("RESOLVE_EXISTING_UPDATE_PRICE", 0),
        "MANUAL_REVIEW_RESOLVED_SERVICE": acts.get("MAP_TO_SERVICES", 0),
        "MANUAL_REVIEW_RESOLVED_NON_PRODUCT": acts.get("IGNORE_NON_PRODUCT", 0),
        "MANUAL_REVIEW_RESOLVED_VALID_PRICE": acts.get("CREATE_PIÑARIA_PRODUCT", 0),
        "NEW_PIÑARIA_PRODUCTS_CREATED": "DRY_RUN",
        "MANUAL_REVIEW_REMAINING": acts.get("KEEP_MANUAL_REVIEW", 0),
        "MISSING_VALID_PRICE_BEFORE": reason_counts.get("MISSING_VALID_PRICE", 0),
        "MISSING_VALID_PRICE_REMAINING": len(missing_rem),
        "PRICE_OUTLIERS_BEFORE": reason_counts.get("PRICE_OUTLIER_REVIEW", 0),
        "PRICE_OUTLIERS_RESOLVED": sum(
            1 for r in outliers if r["ACTION"] != "KEEP_MANUAL_REVIEW"
        ),
        "PRICE_OUTLIERS_REMAINING": sum(
            1 for r in outliers if r["ACTION"] == "KEEP_MANUAL_REVIEW"
        ),
        "PRICE_COLUMN_AMBIGUOUS_BEFORE": reason_counts.get("PRICE_COLUMN_AMBIGUOUS", 0),
        "PRICE_COLUMN_AMBIGUOUS_RESOLVED": sum(
            1 for r in ambig_col if r["ACTION"] != "KEEP_MANUAL_REVIEW"
        ),
        "PRICE_COLUMN_AMBIGUOUS_REMAINING": sum(
            1 for r in ambig_col if r["ACTION"] == "KEEP_MANUAL_REVIEW"
        ),
        "AMBIGUOUS_MATCH_BEFORE": reason_counts.get("AMBIGUOUS_MATCH", 0),
        "AMBIGUOUS_MATCH_RESOLVED": sum(
            1 for r in ambig_match if r["ACTION"] != "KEEP_MANUAL_REVIEW"
        ),
        "NEW_CLASSIFICATION_COUNTS": dict(classes),
        "ACTION_COUNTS": dict(acts),
        "POST_IMPORT_CONFIRMED_DUPLICATES": sum(
            1 for d in dups if d["KIND"] == "CONFIRMED_SAME_PRODUCT"
        ),
        "POST_IMPORT_POSSIBLE_DUPLICATES": sum(
            1 for d in dups if d["KIND"] == "POSSIBLE_DUPLICATE"
        ),
        "NAME_ISSUES": len(names),
        "PIÑARIA_ONLY_PRODUCTS": len(pinaria),
        "SHARED_PRODUCTS": len(shared),
        "SERVICIOS_PROFESIONALES": [
            {"id": p["id"], "list_price": p["list_price"]} for p in svc
        ],
        "APPLY_ROWS": len(apply_rows),
        "FINAL_PRODUCT_PHASE2_STATUS": "DRY_RUN_READY",
    }
    (ev2 / "16_phase2_scorecard.json").write_text(
        json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(score, ensure_ascii=False, indent=2))
    print(f"EVIDENCE={ev2} DRY_ROWS={len(dry)} APPLY={len(apply_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
