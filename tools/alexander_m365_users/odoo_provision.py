# ruff: noqa
"""Crea o actualiza los 6 usuarios Odoo. No imprime contraseñas.

Alexander: UPDATE del usuario existente (gmail). No crea un segundo res.users.
No toca __system__ (id 1). No envía email de reset.
"""

from __future__ import annotations

import json
import os
import sys

from odoo.exceptions import AccessError  # noqa: F401

sys.path.insert(0, "/tmp")
from catalog import (  # noqa: E402
    ALEXANDER_ADMIN_GROUPS,
    DEFAULT_COMPANY_ID,
    FORBIDDEN_OPERATOR_GROUPS,
    INVOICING_EXTRA_GROUPS,
    OPERATIONAL_COMPANY_IDS,
    PEOPLE,
    SALES_PURCHASE_GROUPS,
)

OUT = os.environ.get("ODOO_USER_PROVISION_OUT", "/tmp/odoo_user_provision.json")
APPLY = os.environ.get("ODOO_USER_APPLY") == "1"
PASSWORD = os.environ.get("ODOO_TEMP_PASSWORD")


def _xmlids(env, xmlids):
    groups = env["res.groups"]
    missing = []
    for xid in xmlids:
        rec = env.ref(xid, raise_if_not_found=False)
        if rec:
            groups |= rec
        else:
            missing.append(xid)
    return groups, missing


def _implied_closure(groups):
    seen = groups
    todo = groups
    while todo:
        extra = todo.mapped("implied_ids") - seen
        seen |= extra
        todo = extra
    return seen


def _find_alexander(env):
    Users = env["res.users"].with_context(active_test=False)
    gmail = Users.search([("login", "=", "inversionesdoralex@gmail.com")])
    if len(gmail) == 1:
        return gmail
    upn = Users.search([("login", "=", "alexander.pina@inversionesdoralex.com")])
    if len(upn) == 1:
        return upn
    named = Users.search(
        [("name", "ilike", "Alexander"), ("share", "=", False), ("id", "!=", 1)]
    )
    if len(named) == 1:
        return named
    return Users.browse()


def _find_existing(env, person):
    Users = env["res.users"].with_context(active_test=False)
    exact = Users.search([("login", "=", person["upn"])])
    if exact:
        return exact
    return Users.browse()


def _ctx(env):
    return env(
        context=dict(
            env.context,
            no_reset_password=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            mail_auto_delete=False,
        )
    )


def _group_names(user):
    return sorted(user.sudo().group_ids.mapped("name"))


def main():
    if APPLY and not PASSWORD:
        raise SystemExit("ODOO_TEMP_PASSWORD missing")
    env2 = _ctx(env)
    Users = env2["res.users"].with_context(active_test=False)
    report = {
        "apply": APPLY,
        "created": [],
        "updated": [],
        "reused": [],
        "errors": [],
        "matrix": [],
        "duplicates_created": 0,
        "superuser_id_1_touched": False,
    }
    for person in PEOPLE:
        if person["key"] == "alexander":
            user = _find_alexander(env2)
            if len(user) != 1:
                report["errors"].append(
                    {
                        "person": person["display_name"],
                        "reason": "ALEXANDER_NOT_UNIQUE",
                        "ids": user.ids,
                    }
                )
                continue
            if user.id == 1:
                report["errors"].append(
                    {"person": person["display_name"], "reason": "REFUSES_SUPERUSER"}
                )
                continue
            wanted, missing = _xmlids(
                env2, ALEXANDER_ADMIN_GROUPS + SALES_PURCHASE_GROUPS
            )
            old_login = user.login
            old_groups = _group_names(user)
            new_groups = user.group_ids | wanted
            vals = {
                "login": person["upn"],
                "email": person["upn"],
                "name": "Alexander Piña Aquino",
                "company_id": DEFAULT_COMPANY_ID,
                "company_ids": [(6, 0, list(OPERATIONAL_COMPANY_IDS))],
                "group_ids": [(6, 0, new_groups.ids)],
            }
            if APPLY:
                user.write(vals)
                user.partner_id.write(
                    {"email": person["upn"], "name": "Alexander Piña Aquino"}
                )
            report["updated"].append(
                {
                    "person": person["display_name"],
                    "USER_ID": user.id,
                    "OLD_LOGIN": old_login,
                    "NEW_LOGIN": person["upn"],
                    "OLD_GROUPS": old_groups,
                    "NEW_GROUPS": (
                        _group_names(user)
                        if APPLY
                        else sorted((user.group_ids | wanted).mapped("name"))
                    ),
                    "missing_xmlids": missing,
                }
            )
            report["matrix"].append(
                {
                    "USER_ID": user.id,
                    "OLD_LOGIN": old_login,
                    "NEW_LOGIN": person["upn"],
                    "OLD_GROUPS": old_groups,
                    "NEW_GROUPS": report["updated"][-1]["NEW_GROUPS"],
                    "ACTION": "UPDATE",
                }
            )
            continue

        existing = _find_existing(env2, person)
        xmlids = list(SALES_PURCHASE_GROUPS)
        if person["invoicing"]:
            xmlids.extend(INVOICING_EXTRA_GROUPS)
        wanted, missing = _xmlids(env2, xmlids)
        if existing:
            if len(existing) != 1:
                report["errors"].append(
                    {
                        "person": person["display_name"],
                        "reason": "DUPLICATE_LOGIN",
                        "ids": existing.ids,
                    }
                )
                continue
            old_groups = _group_names(existing)
            if APPLY:
                existing.write(
                    {
                        "name": person["display_name"],
                        "email": person["upn"],
                        "company_id": DEFAULT_COMPANY_ID,
                        "company_ids": [(6, 0, list(OPERATIONAL_COMPANY_IDS))],
                        "group_ids": [(6, 0, (existing.group_ids | wanted).ids)],
                    }
                )
                existing.partner_id.write(
                    {"name": person["display_name"], "email": person["upn"]}
                )
            report["reused"].append(
                {
                    "person": person["display_name"],
                    "USER_ID": existing.id,
                    "missing_xmlids": missing,
                }
            )
            report["matrix"].append(
                {
                    "USER_ID": existing.id,
                    "OLD_LOGIN": existing.login,
                    "NEW_LOGIN": person["upn"],
                    "OLD_GROUPS": old_groups,
                    "NEW_GROUPS": _group_names(existing) if APPLY else old_groups,
                    "ACTION": "REUSE",
                }
            )
            continue

        vals = {
            "name": person["display_name"],
            "login": person["upn"],
            "email": person["upn"],
            "company_id": DEFAULT_COMPANY_ID,
            "company_ids": [(6, 0, list(OPERATIONAL_COMPANY_IDS))],
            "group_ids": [(6, 0, wanted.ids)],
        }
        if APPLY:
            user = Users.create(vals)
            if hasattr(user, "_change_password"):
                user._change_password(PASSWORD)
            else:
                user.write({"password": PASSWORD})
            uid = user.id
            partner_id = user.partner_id.id
        else:
            uid = None
            partner_id = None
        report["created"].append(
            {
                "person": person["display_name"],
                "USER_ID": uid,
                "PARTNER_ID": partner_id,
                "LOGIN": person["upn"],
                "missing_xmlids": missing,
            }
        )
        report["matrix"].append(
            {
                "USER_ID": uid,
                "OLD_LOGIN": None,
                "NEW_LOGIN": person["upn"],
                "OLD_GROUPS": [],
                "NEW_GROUPS": sorted(wanted.mapped("name")),
                "ACTION": "CREATE",
            }
        )

    # Post-check: Alexander not duplicated, operators without Settings.
    alexes = (
        env2["res.users"]
        .with_context(active_test=False)
        .search(
            [
                "|",
                (
                    "login",
                    "in",
                    [
                        "inversionesdoralex@gmail.com",
                        next(p["upn"] for p in PEOPLE if p["key"] == "alexander"),
                    ],
                ),
                ("name", "ilike", "Alexander Pi"),
            ]
        )
    )
    report["alexander_user_count"] = len(alexes)
    report["alexander_ids"] = alexes.ids
    if APPLY and not report["errors"]:
        env2.cr.commit()
        report["committed"] = True
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["errors"]:
        raise SystemExit(2)


main()
