"""Asigna O365_BUSINESS_PREMIUM (Standard actual del tenant) a los 6 UPN.

No toca admin@ ni alex@ onmicrosoft. No quita licencias superiores.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from catalog import DO_NOT_TOUCH_M365, PEOPLE, SUPERIOR_EXCHANGE_PART_NUMBERS
from graph_client import call, get_user, token

STANDARD_PART = "O365_BUSINESS_PREMIUM"
OUT = Path(os.environ.get("M365_LICENSE_OUT", "/tmp/m365_standard_license.json"))


def _skus(tok):
    st, data = call(
        tok,
        "GET",
        "/subscribedSkus?$select=skuId,skuPartNumber,prepaidUnits,consumedUnits",
    )
    rows = []
    if st == 200:
        for s in data.get("value") or []:
            prepaid = (s.get("prepaidUnits") or {}).get("enabled") or 0
            consumed = s.get("consumedUnits") or 0
            rows.append(
                {
                    "skuPartNumber": s.get("skuPartNumber"),
                    "skuId": s.get("skuId"),
                    "prepaidUnits": prepaid,
                    "consumedUnits": consumed,
                    "availableUnits": prepaid - consumed,
                }
            )
    return rows


def _licenses(tok, user_id):
    st, data = call(tok, "GET", "/users/%s/licenseDetails" % user_id)
    if st != 200:
        return []
    return [x.get("skuPartNumber") for x in data.get("value") or []]


def main():
    tok = token()
    skus = _skus(tok)
    standard = next((s for s in skus if s["skuPartNumber"] == STANDARD_PART), None)
    report = {
        "sku_requested": STANDARD_PART,
        "sku": standard,
        "skus_before": skus,
        "assigned": [],
        "skipped": [],
        "errors": [],
        "untouched": list(DO_NOT_TOUCH_M365),
    }
    if not standard:
        report["errors"].append({"reason": "STANDARD_SKU_NOT_IN_TENANT"})
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit(2)
    needed = 0
    for person in PEOPLE:
        if person["upn"] in DO_NOT_TOUCH_M365:
            continue
        st, user = get_user(tok, person["upn"])
        if st != 200:
            report["errors"].append({"upn": person["upn"], "status": st})
            continue
        current = _licenses(tok, user["id"])
        if STANDARD_PART in current:
            report["skipped"].append(
                {
                    "upn": person["upn"],
                    "reason": "ALREADY_HAS_STANDARD",
                    "licenses": current,
                }
            )
            continue
        if any(
            p in SUPERIOR_EXCHANGE_PART_NUMBERS for p in current if p != STANDARD_PART
        ):
            report["skipped"].append(
                {
                    "upn": person["upn"],
                    "reason": "KEEP_EXISTING_EXCHANGE_LICENSE",
                    "licenses": current,
                }
            )
            continue
        needed += 1
    if standard["availableUnits"] < needed:
        report["errors"].append(
            {
                "reason": "NOT_ENOUGH_UNITS",
                "available": standard["availableUnits"],
                "needed": needed,
            }
        )
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit(3)
    for person in PEOPLE:
        if person["upn"] in DO_NOT_TOUCH_M365:
            continue
        st, user = get_user(tok, person["upn"])
        if st != 200:
            continue
        current = _licenses(tok, user["id"])
        if STANDARD_PART in current or any(
            p in SUPERIOR_EXCHANGE_PART_NUMBERS for p in current if p != STANDARD_PART
        ):
            continue
        st_p, loc = call(
            tok,
            "GET",
            "/users/%s?$select=usageLocation" % urllib.parse.quote(person["upn"]),
        )
        if st_p == 200 and loc.get("usageLocation") != "DO":
            call(
                tok,
                "PATCH",
                "/users/%s" % urllib.parse.quote(person["upn"]),
                {"usageLocation": "DO"},
            )
        st_a, data = call(
            tok,
            "POST",
            "/users/%s/assignLicense" % user["id"],
            {
                "addLicenses": [{"skuId": standard["skuId"], "disabledPlans": []}],
                "removeLicenses": [],
            },
        )
        if st_a in (200, 202):
            report["assigned"].append({"upn": person["upn"], "id": user["id"]})
        else:
            report["errors"].append(
                {"upn": person["upn"], "status": st_a, "error": data}
            )
    report["skus_after"] = _skus(tok)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "assigned": [x["upn"] for x in report["assigned"]],
                "skipped": report["skipped"],
                "errors": report["errors"],
                "sku_after": next(
                    (
                        s
                        for s in report["skus_after"]
                        if s["skuPartNumber"] == STANDARD_PART
                    ),
                    None,
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if report["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
