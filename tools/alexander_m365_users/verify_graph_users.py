"""Verifica UPN, enabled, UsageLocation, roles, licencia y buzón."""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from catalog import DO_NOT_TOUCH_M365, PEOPLE
from graph_client import call, get_user, token

OUT = Path(os.environ.get("M365_VERIFY_OUT", "/tmp/m365_users_verify.json"))
SELECT = (
    "id,displayName,userPrincipalName,accountEnabled,usageLocation,mail,"
    "proxyAddresses,assignedLicenses,passwordProfile"
)


def _roles(tok, user_id):
    st, data = call(
        tok,
        "GET",
        "/users/%s/memberOf/microsoft.graph.directoryRole" % user_id,
    )
    if st != 200:
        return st, []
    names = [r.get("displayName") for r in data.get("value") or []]
    return st, names


def _licenses(tok, user_id):
    st, data = call(tok, "GET", "/users/%s/licenseDetails" % user_id)
    if st != 200:
        return []
    return [x.get("skuPartNumber") for x in data.get("value") or []]


def _mailbox(tok, user_id, upn):
    st, data = call(tok, "GET", "/users/%s/mailboxSettings" % user_id)
    if st == 200:
        return "CREATED", data.get("userPurpose")
    st2, user = call(
        tok,
        "GET",
        "/users/%s?$select=mail,proxyAddresses" % urllib.parse.quote(upn),
    )
    mail = user.get("mail") if st2 == 200 else None
    proxies = user.get("proxyAddresses") if st2 == 200 else []
    if mail or proxies:
        return "PROVISIONING_OR_PARTIAL", mail
    return "NOT_CREATED", None


def main():
    tok = token()
    rows = []
    for person in PEOPLE:
        st, data = get_user(tok, person["upn"])
        if st != 200:
            rows.append(
                {
                    "person": person["display_name"],
                    "upn": person["upn"],
                    "exists": False,
                    "status": st,
                }
            )
            continue
        uid = data["id"]
        st_d, detail = call(
            tok,
            "GET",
            "/users/%s?$select=%s" % (urllib.parse.quote(person["upn"]), SELECT),
        )
        if st_d != 200:
            st_d, detail = call(
                tok,
                "GET",
                "/users/%s?$select=id,displayName,userPrincipalName,accountEnabled,usageLocation,mail,proxyAddresses,assignedLicenses"
                % urllib.parse.quote(person["upn"]),
            )
        info = detail if st_d == 200 else data
        role_st, roles = _roles(tok, uid)
        licenses = _licenses(tok, uid)
        mailbox_status, purpose = _mailbox(tok, uid, person["upn"])
        pwd = info.get("passwordProfile") or {}
        primary = info.get("mail")
        rows.append(
            {
                "person": person["display_name"],
                "DISPLAY_NAME": info.get("displayName"),
                "UPN": info.get("userPrincipalName"),
                "ACCOUNT_ENABLED": info.get("accountEnabled"),
                "USAGE_LOCATION": info.get("usageLocation"),
                "LICENSE": licenses or None,
                "MAILBOX_STATUS": mailbox_status,
                "MAILBOX_PURPOSE": purpose,
                "PRIMARY_SMTP": primary,
                "FORCE_PASSWORD_CHANGE": pwd.get("forceChangePasswordNextSignIn"),
                "ADMIN_ROLES": roles or "NONE",
                "role_query_status": role_st,
                "id": uid,
            }
        )
    related = []
    for upn in DO_NOT_TOUCH_M365:
        st, data = get_user(tok, upn)
        if st == 200:
            _, roles = _roles(tok, data["id"])
            related.append(
                {
                    "upn": upn,
                    "displayName": data.get("displayName"),
                    "roles": roles or "NONE",
                    "password_reset": False,
                }
            )
    report = {"users": rows, "untouched": related}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
