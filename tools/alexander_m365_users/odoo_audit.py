# ruff: noqa
"""Auditoría res.users / res.partner antes de crear. No escribe."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/tmp")
from catalog import (  # noqa: E402
    DEFAULT_COMPANY_ID,
    OPERATIONAL_COMPANY_IDS,
    PEOPLE,
)

OUT = os.environ.get("ODOO_USER_AUDIT_OUT", "/tmp/odoo_user_audit.json")


def _needles(person):
    items = [person["upn"], person["display_name"], *person.get("search_needles", ())]
    if person.get("known_odoo_login"):
        items.append(person["known_odoo_login"])
    return tuple(dict.fromkeys(items))


def _search_users(env, needles):
    Users = env["res.users"].with_context(active_test=False)
    found = Users.browse()
    for n in needles:
        found |= Users.search(
            [
                "|",
                "|",
                ("login", "ilike", n),
                ("name", "ilike", n),
                ("email", "ilike", n),
            ]
        )
    return found


def _search_partners(env, needles):
    Partners = env["res.partner"].with_context(active_test=False)
    found = Partners.browse()
    for n in needles:
        found |= Partners.search(["|", ("name", "ilike", n), ("email", "ilike", n)])
    return found


def _action(person, users):
    if person["key"] == "alexander":
        gmail = users.filtered(lambda u: u.login == "inversionesdoralex@gmail.com")
        if len(gmail) == 1:
            return "UPDATE", gmail
        named = users.filtered(
            lambda u: "alexander" in (u.name or "").lower() and not u.share
        )
        if len(named) == 1:
            return "UPDATE", named
        if not users:
            return "CONFLICT", users
        return "CONFLICT", users
    internals = users.filtered(lambda u: not u.share)
    if not internals:
        return "CREATE", internals
    exact = internals.filtered(lambda u: u.login == person["upn"])
    if len(exact) == 1:
        return "REUSE", exact
    if len(internals) == 1:
        return "CONFLICT", internals
    return "CONFLICT", internals


def main():
    rows = []
    conflicts = 0
    for person in PEOPLE:
        needles = _needles(person)
        users = _search_users(env, needles)
        # Evitar falso positivo: "aquino" de Luis no debe capturar a Alexander.
        if person["key"] == "luis":
            users = users.filtered(
                lambda u: "luis" in (u.name or "").lower()
                or "luis" in (u.login or "").lower()
                or u.login == person["upn"]
            )
        partners = _search_partners(env, needles)
        if person["key"] == "luis":
            partners = partners.filtered(
                lambda p: "luis" in (p.name or "").lower()
                or (p.email or "") == person["upn"]
            )
        action, chosen = _action(person, users)
        if action == "CONFLICT":
            conflicts += 1
        rows.append(
            {
                "PERSON": person["display_name"],
                "EXISTING_USER_ID": chosen.ids if chosen else [],
                "EXISTING_PARTNER_ID": partners.ids,
                "EXISTING_LOGIN": [u.login for u in users],
                "EXISTING_EMAIL": [u.email for u in users],
                "EXISTING_NAMES": [u.name for u in users],
                "PARTNER_NAMES": [p.name for p in partners],
                "ACTION": action,
                "DEFAULT_COMPANY": chosen.company_id.id if len(chosen) == 1 else None,
                "ALLOWED_COMPANIES": (
                    chosen.company_ids.ids if len(chosen) == 1 else None
                ),
            }
        )

    all_users = []
    for u in (
        env["res.users"]
        .with_context(active_test=False)
        .search([("share", "=", False)], order="id")
    ):
        all_users.append(
            {
                "id": u.id,
                "login": u.login,
                "name": u.name,
                "active": u.active,
                "company": u.company_id.id,
                "companies": u.company_ids.ids,
                "settings": u.has_group("base.group_system"),
                "groups": sorted(
                    u.group_ids.mapped("full_name")
                    if "full_name" in u.group_ids._fields
                    else u.group_ids.mapped("name")
                ),
            }
        )
    mail_servers = (
        env["ir.mail_server"].search_count([]) if "ir.mail_server" in env else 0
    )
    companies = [
        {"id": c.id, "name": c.name}
        for c in env["res.company"].browse(list(OPERATIONAL_COMPANY_IDS))
    ]
    report = {
        "people": rows,
        "conflicts": conflicts,
        "all_internal_users": all_users,
        "operational_companies": companies,
        "default_company_id": DEFAULT_COMPANY_ID,
        "ir_mail_server": mail_servers,
        "ODOO_PASSWORD_RESET_READY": "YES" if mail_servers else "NO",
        "create_allowed": conflicts == 0,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


main()
