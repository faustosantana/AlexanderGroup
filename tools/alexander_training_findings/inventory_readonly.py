# ruff: noqa
"""READ-ONLY environment inventory. No writes, no commits."""

import json
import os

try:
    from odoo.release import version as odoo_version
except Exception:
    odoo_version = "?"

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
Mod = env["ir.module.module"].sudo()
installed = Mod.search([("state", "=", "installed")], order="name")


def pack(mods):
    return [
        {
            "name": m.name,
            "shortdesc": m.shortdesc or "",
            "author": (m.author or "")[:80],
            "version": m.latest_version or "",
            "application": bool(m.application),
        }
        for m in mods
    ]


def by_prefix(prefixes):
    return pack(
        installed.filtered(lambda m: any(m.name.startswith(p) for p in prefixes))
    )


pg = "?"
try:
    env.cr.execute("SHOW server_version")
    pg = env.cr.fetchone()[0]
except Exception as exc:
    pg = str(exc)

addons_path = []
try:
    import odoo.addons

    addons_path = list(getattr(odoo.addons, "__path__", []))
except Exception:
    pass

companies = []
for c in env["res.company"].sudo().search([]):
    companies.append(
        {
            "id": c.id,
            "name": c.name,
            "vat": c.vat or "",
            "currency": c.currency_id.name if c.currency_id else "",
            "email": c.email or "",
            "website": c.website or "",
            "active": bool(getattr(c, "active", True)),
        }
    )

users = []
for u in (
    env["res.users"]
    .sudo()
    .with_context(active_test=False)
    .search([("share", "=", False)], order="login")
):
    groups = []
    gfield = "group_ids" if "group_ids" in u._fields else "groups_id"
    for g in u[gfield]:
        xmlids = g.get_external_id()
        groups.append(xmlids.get(g.id) or g.name)
    users.append(
        {
            "id": u.id,
            "login": u.login,
            "name": u.name,
            "active": bool(u.active),
            "company": u.company_id.name if u.company_id else "",
            "companies": [c.name for c in u.company_ids],
            "groups": sorted(groups),
        }
    )

print(
    json.dumps(
        {
            "DATABASE": env.cr.dbname,
            "ODOO_VERSION": odoo_version,
            "POSTGRES": pg,
            "ADDONS_PATH": addons_path,
            "COMPANIES": companies,
            "INSTALLED_COUNT": len(installed),
            "JUSTECH": by_prefix(("justech",)),
            "L10N_DO": by_prefix(("l10n_do", "justech_l10n_do")),
            "SALE": pack(
                installed.filtered(
                    lambda m: m.name.startswith("sale") or "sale" in m.name
                )
            ),
            "PURCHASE": pack(
                installed.filtered(
                    lambda m: m.name.startswith("purchase") or "purchase" in m.name
                )
            ),
            "STOCK": pack(
                installed.filtered(
                    lambda m: m.name.startswith(("stock", "mrp"))
                    or "inventory" in (m.name + (m.shortdesc or "")).lower()
                )
            ),
            "CRM": pack(
                installed.filtered(
                    lambda m: m.name.startswith("crm") or "crm" in m.name
                )
            ),
            "ACCOUNT": pack(
                installed.filtered(
                    lambda m: m.name.startswith(("account", "l10n"))
                    or "account" in m.name
                )
            ),
            "APPROVAL": pack(
                installed.filtered(
                    lambda m: "approv" in m.name
                    or "approval" in (m.shortdesc or "").lower()
                )
            ),
            "MAIL": pack(
                installed.filtered(
                    lambda m: m.name.startswith(
                        ("mail", "fetchmail", "microsoft_outlook")
                    )
                    or "mail" in m.name
                )
            ),
            "WEBSITE": pack(installed.filtered(lambda m: m.name.startswith("website"))),
            "REPORT": pack(
                installed.filtered(lambda m: "report" in m.name or "document" in m.name)
            ),
            "MARGIN_TRACE_RECOVERY_SECURITY": pack(
                installed.filtered(
                    lambda m: any(
                        k in m.name
                        for k in (
                            "margin",
                            "trace",
                            "recovery",
                            "security",
                            "audit",
                            "accounting_recovery",
                        )
                    )
                )
            ),
            "ALL_INSTALLED": [m.name for m in installed],
            "USERS": users,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
