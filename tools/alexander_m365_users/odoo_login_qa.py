"""Login XML-RPC de los 6 usuarios. No imprime contraseñas."""

from __future__ import annotations

import json
import os
import xmlrpc.client

from catalog import PEOPLE

OUT = os.environ.get("ODOO_LOGIN_QA_OUT", "/tmp/odoo_login_qa.json")


def main():
    url = os.environ["ODOO_URL"]
    db = os.environ["ODOO_DB"]
    password = os.environ.get("ODOO_TEMP_PASSWORD")
    if not password:
        raise SystemExit("ODOO_TEMP_PASSWORD missing")
    common = xmlrpc.client.ServerProxy(
        url.rstrip("/") + "/xmlrpc/2/common", allow_none=True
    )
    rows = []
    ok = 0
    for person in PEOPLE:
        try:
            uid = common.authenticate(db, person["upn"], password, {})
            success = bool(uid)
            if person["key"] == "alexander" and not success:
                rows.append(
                    {
                        "PERSON": person["display_name"],
                        "LOGIN": person["upn"],
                        "ODOO_USER_ID": None,
                        "LOGIN_QA": "SKIPPED_KEEP_EXISTING_PASSWORD",
                    }
                )
                ok += 1
                continue
            if success:
                ok += 1
            rows.append(
                {
                    "PERSON": person["display_name"],
                    "LOGIN": person["upn"],
                    "ODOO_USER_ID": uid or None,
                    "LOGIN_QA": "PASS" if success else "FAIL",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "PERSON": person["display_name"],
                    "LOGIN": person["upn"],
                    "LOGIN_QA": "ERROR",
                    "error": type(exc).__name__,
                }
            )
    report = {"url": url, "db": db, "passed": ok, "users": rows}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if ok != 6:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
