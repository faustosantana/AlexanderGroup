# ruff: noqa
"""Crea usuarios Entra si no existen. No imprime tokens ni passwords.

No asigna SKU inventado. Si no hay EXCHANGEDESKLESS, deja el usuario
sin licencia y reporta mailbox pendiente.
No toca admin@ / alex@ doralex.onmicrosoft.com.
No resetea un usuario Microsoft que ya existiera.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from catalog import DO_NOT_TOUCH_M365, KIOSK_PART_NUMBERS, PEOPLE
from graph_client import call, get_user, token

OUT = Path(os.environ.get("M365_PROVISION_OUT", "/tmp/m365_users_provision.json"))


def _kiosk(tok):
    st, skus = call(
        tok,
        "GET",
        "/subscribedSkus?$select=skuId,skuPartNumber,prepaidUnits,consumedUnits",
    )
    if st != 200:
        return None
    for s in skus.get("value", []):
        if s.get("skuPartNumber") in KIOSK_PART_NUMBERS:
            prepaid = (s.get("prepaidUnits") or {}).get("enabled") or 0
            consumed = s.get("consumedUnits") or 0
            return {
                "skuPartNumber": s.get("skuPartNumber"),
                "skuId": s.get("skuId"),
                "prepaidUnits": prepaid,
                "consumedUnits": consumed,
                "availableUnits": prepaid - consumed,
            }
    return None


def main():
    password = os.environ.get("M365_TEMP_PASSWORD")
    if not password:
        raise SystemExit("M365_TEMP_PASSWORD missing")
    tok = token()
    kiosk = _kiosk(tok)
    report = {
        "kiosk_sku": kiosk,
        "created": [],
        "reused": [],
        "errors": [],
        "conflicts": [],
        "licenses_assigned": 0,
        "existing_related": [
            {"upn": u, "note": "NO TOCADO"} for u in DO_NOT_TOUCH_M365
        ],
    }
    for row in PEOPLE:
        if row["upn"] in DO_NOT_TOUCH_M365:
            report["conflicts"].append(
                {"upn": row["upn"], "reason": "protected_account"}
            )
            continue
        st, existing = get_user(tok, row["upn"])
        if st == 200:
            report["reused"].append(
                {
                    "upn": row["upn"],
                    "id": existing.get("id"),
                    "displayName": existing.get("displayName"),
                    "action": "REUSE",
                    "password_reset": False,
                }
            )
            continue
        payload = {
            "accountEnabled": True,
            "displayName": row["display_name"],
            "givenName": row["given"],
            "surname": row["surname"],
            "mailNickname": row["mail_nickname"],
            "userPrincipalName": row["upn"],
            "usageLocation": "DO",
            "passwordProfile": {
                "password": password,
                "forceChangePasswordNextSignIn": True,
            },
        }
        st, data = call(tok, "POST", "/users", payload)
        if st in (200, 201):
            report["created"].append(
                {
                    "upn": row["upn"],
                    "id": data.get("id"),
                    "displayName": data.get("displayName"),
                    "usageLocation": data.get("usageLocation") or "DO",
                    "forceChangePasswordNextSignIn": True,
                    "license": None,
                    "mailbox": (
                        "PENDING_NO_KIOSK_SKU" if not kiosk else "PENDING_ASSIGN"
                    ),
                }
            )
        else:
            report["errors"].append({"upn": row["upn"], "status": st, "error": data})
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "created": len(report["created"]),
                "reused": len(report["reused"]),
                "errors": report["errors"],
                "conflicts": report["conflicts"],
                "kiosk": report["kiosk_sku"],
                "created_upns": [x["upn"] for x in report["created"]],
                "reused_upns": [x["upn"] for x in report["reused"]],
            },
            indent=2,
        )
    )
    if report["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
