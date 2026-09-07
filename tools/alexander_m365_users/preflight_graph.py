"""Preflight Microsoft: dominio verificado, SKUs, usuarios existentes."""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from catalog import DO_NOT_TOUCH_M365, KIOSK_PART_NUMBERS, M365_DOMAIN, PEOPLE
from graph_client import call, get_user, token

OUT = Path(os.environ.get("M365_PREFLIGHT_OUT", "/tmp/m365_preflight.json"))


def _sku_row(sku: dict) -> dict:
    prepaid = (sku.get("prepaidUnits") or {}).get("enabled") or 0
    consumed = sku.get("consumedUnits") or 0
    return {
        "skuPartNumber": sku.get("skuPartNumber"),
        "skuId": sku.get("skuId"),
        "prepaidUnits": prepaid,
        "consumedUnits": consumed,
        "availableUnits": prepaid - consumed,
        "servicePlans": [
            p.get("servicePlanName")
            for p in sku.get("servicePlans") or []
            if p.get("provisioningStatus") == "Success" or p.get("appliesTo") == "User"
        ],
    }


def main():
    tok = token()
    st, domains = call(tok, "GET", "/domains")
    domain_rows = []
    verified = False
    if st == 200:
        for d in domains.get("value", []):
            row = {
                "id": d.get("id"),
                "isVerified": d.get("isVerified"),
                "isDefault": d.get("isDefault"),
                "authenticationType": d.get("authenticationType"),
            }
            domain_rows.append(row)
            if d.get("id") == M365_DOMAIN and d.get("isVerified"):
                verified = True
    st, skus = call(
        tok,
        "GET",
        "/subscribedSkus?$select=skuId,skuPartNumber,prepaidUnits,consumedUnits,servicePlans",
    )
    sku_rows = [_sku_row(s) for s in (skus.get("value") or [])] if st == 200 else []
    kiosk = next(
        (s for s in sku_rows if s["skuPartNumber"] in KIOSK_PART_NUMBERS), None
    )
    people_lookup = []
    for person in PEOPLE:
        st_u, data = get_user(tok, person["upn"])
        hits = []
        if st_u == 200:
            hits.append(
                {
                    "via": "upn",
                    "id": data.get("id"),
                    "upn": data.get("userPrincipalName"),
                    "displayName": data.get("displayName"),
                    "mail": data.get("mail"),
                    "accountEnabled": data.get("accountEnabled"),
                }
            )
        query = urllib.parse.urlencode(
            {
                "$filter": "displayName eq '%s'"
                % person["display_name"].replace("'", "''"),
                "$select": "id,displayName,userPrincipalName,mail",
            }
        )
        st_s, search = call(tok, "GET", "/users?%s" % query)
        if st_s == 200:
            for u in search.get("value") or []:
                if u.get("userPrincipalName") != person["upn"]:
                    hits.append(
                        {
                            "via": "displayName",
                            "id": u.get("id"),
                            "upn": u.get("userPrincipalName"),
                            "displayName": u.get("displayName"),
                            "mail": u.get("mail"),
                        }
                    )
        mail_q = urllib.parse.urlencode(
            {
                "$filter": "mail eq '%s'" % person["upn"],
                "$select": "id,displayName,userPrincipalName,mail",
            }
        )
        st_m, mail_hits = call(tok, "GET", "/users?%s" % mail_q)
        if st_m == 200:
            for u in mail_hits.get("value") or []:
                if u.get("userPrincipalName") != person["upn"]:
                    hits.append(
                        {
                            "via": "mail",
                            "id": u.get("id"),
                            "upn": u.get("userPrincipalName"),
                            "displayName": u.get("displayName"),
                            "mail": u.get("mail"),
                        }
                    )
        people_lookup.append(
            {
                "person": person["display_name"],
                "requested_upn": person["upn"],
                "exists_exact_upn": st_u == 200,
                "hits": hits,
                "action": "REUSE" if st_u == 200 else "CREATE",
            }
        )
    related = []
    for upn in DO_NOT_TOUCH_M365:
        st_r, data = get_user(tok, upn)
        related.append(
            {
                "upn": upn,
                "exists": st_r == 200,
                "displayName": data.get("displayName") if st_r == 200 else None,
                "accountEnabled": data.get("accountEnabled") if st_r == 200 else None,
                "touch": "NO",
            }
        )
    report = {
        "M365_DOMAIN": M365_DOMAIN,
        "DOMAIN_VERIFIED": "YES" if verified else "NO",
        "domains": domain_rows,
        "skus": sku_rows,
        "kiosk": kiosk,
        "people": people_lookup,
        "do_not_touch": related,
        "create_allowed": verified,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "DOMAIN_VERIFIED": report["DOMAIN_VERIFIED"],
                "create_allowed": verified,
                "kiosk": kiosk,
                "sku_part_numbers": [s["skuPartNumber"] for s in sku_rows],
                "people": [
                    {
                        "person": p["person"],
                        "upn": p["requested_upn"],
                        "exists": p["exists_exact_upn"],
                        "extra_hits": len(p["hits"])
                        - (1 if p["exists_exact_upn"] else 0),
                        "action": p["action"],
                    }
                    for p in people_lookup
                ],
                "do_not_touch": related,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not verified:
        raise SystemExit("STOP MICROSOFT USER CREATION: domain not verified")


if __name__ == "__main__":
    main()
