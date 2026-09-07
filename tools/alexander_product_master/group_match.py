from __future__ import annotations

from collections import defaultdict

from .classify import (
    category_for,
    extract_brand,
    extract_specs,
    identity_key,
    is_food,
    is_meat,
    is_service,
    map_uom,
)
from .prices import pick_max_price, unit_price_excl_tax
from .textutil import collapse, title_es


def enrich(row: dict) -> dict:
    desc = row["raw_description"]
    price, status = unit_price_excl_tax(row)
    service = is_service(desc)
    food = is_food(desc)
    meat = is_meat(desc)
    out = dict(row)
    out.update(
        {
            "normalized": collapse(desc),
            "brand": extract_brand(desc),
            "specs": extract_specs(desc),
            "identity": identity_key(desc),
            "is_service": service,
            "is_food": food,
            "is_meat": meat,
            "category": category_for(desc, service, food, meat),
            "uom": map_uom(row.get("uom_raw") or ""),
            "price_excl_tax": price,
            "price_status": status,
        }
    )
    return out


def group_rows(rows: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["is_service"]:
            buckets["SERVICE::profesional"].append(row)
        else:
            buckets[row["identity"]].append(row)
    groups = []
    gid = 1
    for key, items in buckets.items():
        service = all(i["is_service"] for i in items) or key.startswith("SERVICE")
        food = any(i["is_food"] for i in items) and not service
        meat = any(i["is_meat"] for i in items) and not service
        prices = [i["price_excl_tax"] for i in items if i["price_excl_tax"]]
        valid_docs = [
            i
            for i in items
            if i["price_excl_tax"] and i["document_type"] != "COST_ANALYSIS"
        ]
        currencies = {
            i.get("currency") or "DOP" for i in items if i.get("currency") != "MIXED"
        }
        mixed = any(i.get("currency") == "MIXED" for i in items) or (
            "USD" in {i.get("currency") for i in items}
            and "DOP" in {i.get("currency") for i in items}
        )
        max_price, price_rule = pick_max_price(prices)
        evidence = None
        if max_price and valid_docs:
            evidence = max(valid_docs, key=lambda i: i["price_excl_tax"] or 0)
        name_src = min(items, key=lambda i: len(i["raw_description"]))
        name = (
            "Servicios profesionales"
            if service
            else title_es(name_src["raw_description"])
        )
        groups.append(
            {
                "canonical_id": f"AG-{gid:04d}",
                "identity": key,
                "canonical_name": name,
                "is_service": service,
                "is_food": food,
                "is_meat": meat,
                "category": "Servicios" if service else items[0]["category"],
                "uom": "Units" if service else items[0]["uom"],
                "brand": "" if service else items[0]["brand"],
                "specs": {} if service else items[0]["specs"],
                "company_scope": "PINARIA" if food or meat else "SHARED",
                "occurrences": len(items),
                "prices": prices,
                "historical_min": min(prices) if prices else None,
                "historical_max": max_price,
                "price_rule": price_rule,
                "price_evidence": evidence,
                "currency_conflict": mixed,
                "source_files": sorted({i["source_file"] for i in items}),
                "source_sheets": sorted({i["source_sheet"] for i in items}),
                "rows": items,
            }
        )
        gid += 1
    return groups


def _norm_name(name: str) -> str:
    return collapse(name)


def match_odoo(groups: list[dict], products: list[dict]) -> list[dict]:
    by_norm = {}
    for p in products:
        by_norm.setdefault(_norm_name(p["name"]), []).append(p)
    by_id = {}
    for p in products:
        by_id.setdefault(identity_key(p["name"]), []).append(p)

    for g in groups:
        if g["is_service"]:
            hits = [
                p
                for p in products
                if collapse(p["name"])
                in {"servicios profesionales", "servicio profesional"}
                or (
                    p["type"] == "service"
                    and "servicio" in collapse(p["name"])
                    and "profes" in collapse(p["name"])
                )
            ]
            if hits:
                g["match_type"] = "EXACT_MATCH"
                g["odoo"] = hits[0]
            else:
                g["match_type"] = "NEW_PRODUCT"
                g["odoo"] = None
            continue
        exact = by_norm.get(collapse(g["canonical_name"])) or by_norm.get(
            g["rows"][0]["normalized"]
        )
        if exact and len(exact) == 1:
            g["match_type"] = "EXACT_MATCH"
            g["odoo"] = exact[0]
            continue
        ident = by_id.get(g["identity"])
        if ident and len(ident) == 1:
            g["match_type"] = "SAFE_SEMANTIC_MATCH"
            g["odoo"] = ident[0]
            continue
        if ident and len(ident) > 1:
            g["match_type"] = "AMBIGUOUS_MATCH"
            g["odoo"] = None
            g["review_reason"] = "Multiple Odoo products share identity"
            continue
        # conservative containment
        tokens = set(g["identity"].split("|"))
        near = []
        for p in products:
            pt = set(identity_key(p["name"]).split("|"))
            if tokens and tokens == pt:
                near.append(p)
        if len(near) == 1:
            g["match_type"] = "SAFE_SEMANTIC_MATCH"
            g["odoo"] = near[0]
        elif len(near) > 1:
            g["match_type"] = "AMBIGUOUS_MATCH"
            g["odoo"] = None
            g["review_reason"] = "Several similar Odoo products"
        else:
            g["match_type"] = "NEW_PRODUCT"
            g["odoo"] = None
    return groups


def decide_action(group: dict) -> dict:
    reasons = []
    if group.get("price_rule") == "PRICE_OUTLIER_REVIEW":
        reasons.append("PRICE_OUTLIER_REVIEW")
    if (
        any(r["price_status"] == "PRICE_COLUMN_AMBIGUOUS" for r in group["rows"])
        and not group["historical_max"]
    ):
        reasons.append("PRICE_COLUMN_AMBIGUOUS")
    if group["match_type"] == "AMBIGUOUS_MATCH":
        reasons.append("AMBIGUOUS_MATCH")
    if group.get("currency_conflict"):
        reasons.append("CURRENCY_CONFLICT")
    if (
        not group["is_service"]
        and not group["historical_max"]
        and not group.get("odoo")
    ):
        reasons.append("MISSING_VALID_PRICE")

    current = float(group["odoo"]["list_price"]) if group.get("odoo") else None
    hist = group["historical_max"]
    if group["is_service"]:
        final = 0.0
        action = (
            "MAP_TO_SERVICIOS_PROFESIONALES"
            if group.get("odoo")
            else "MAP_TO_SERVICIOS_PROFESIONALES"
        )
        if group.get("odoo") and current == 0:
            action = (
                "REUSE_NO_CHANGE"
                if group["odoo"]["name"].lower().startswith("servicio")
                else "MAP_TO_SERVICIOS_PROFESIONALES"
            )
        elif group.get("odoo"):
            action = "REUSE_UPDATE_PRICE"
    elif reasons:
        final = max([p for p in [current, hist] if p is not None], default=None)
        action = "MANUAL_REVIEW"
    elif group.get("odoo"):
        final = max(current or 0, hist or 0)
        if hist and current is not None and abs(final - current) < 0.009:
            action = "REUSE_NO_CHANGE"
        elif hist and current is not None and final > current:
            action = "REUSE_UPDATE_PRICE"
        else:
            action = "REUSE_NO_CHANGE"
            final = current
    else:
        if not hist:
            action = "MANUAL_REVIEW"
            reasons.append("MISSING_VALID_PRICE")
            final = None
        elif group["company_scope"] == "PINARIA":
            action = "CREATE_PIÑARIA_PRODUCT"
            final = hist
        else:
            action = "CREATE_SHARED_PRODUCT"
            final = hist

    group["action"] = action
    group["final_list_price"] = final
    group["current_list_price"] = current
    group["review_reason"] = ";".join(reasons) or group.get("review_reason")
    return group
