# ruff: noqa
"""Mapea SOLO provincia y fecha de inicio desde el Excel. No toca CxC/NCF/bancos."""

import json
import re
from pathlib import Path

START_BY_VAT = {
    "132220112": ("2020-11-02", "SANTO DOMINGO"),
    "132271068": ("2021-03-01", "SANTO DOMINGO"),
    "132721502": ("2022-11-09", "DISTRITO NACIONAL"),
    "132710152": ("2022-09-14", "SANTO DOMINGO"),
    "132769155": ("2023-01-19", "SANTO DOMINGO"),
    "133371261": ("2025-04-04", "SANTO DOMINGO"),
}
DRY = False
OUT = "/tmp/op_ready_legal_fix.json"


def _vat(s):
    return re.sub(r"\D", "", str(s or ""))


def find_state(env, country, province):
    State = env["res.country.state"]
    if not country:
        return State
    rec = State.search(
        [("country_id", "=", country.id), ("name", "ilike", province)], limit=1
    )
    if rec:
        return rec
    # common DO aliases
    aliases = {
        "SANTO DOMINGO": ["Santo Domingo", "Provincia Santo Domingo"],
        "DISTRITO NACIONAL": ["Distrito Nacional", "D.N.", "DN"],
    }
    for alias in aliases.get(province, []):
        rec = State.search(
            [("country_id", "=", country.id), ("name", "ilike", alias)], limit=1
        )
        if rec:
            return rec
    return State


def run(env):
    out = {"writes": [], "skipped": [], "states_available": []}
    do = env["res.country"].search([("code", "=", "DO")], limit=1)
    for st in env["res.country.state"].search([("country_id", "=", do.id)]):
        out["states_available"].append({"id": st.id, "name": st.name, "code": st.code})
    for c in env["res.company"].search([("id", "!=", 1)]):
        vat = _vat(c.vat or c.partner_id.vat)
        src = START_BY_VAT.get(vat)
        if not src:
            out["skipped"].append({"company": c.name, "reason": "VAT_NOT_IN_EXCEL"})
            continue
        start, province = src
        vals_company = {}
        vals_partner = {}
        if "l10n_do_dgii_start_date" in c._fields and not c.l10n_do_dgii_start_date:
            vals_company["l10n_do_dgii_start_date"] = start
        p = c.partner_id
        if not p.state_id:
            state = find_state(env, do or p.country_id, province)
            if state:
                vals_partner["state_id"] = state.id
            else:
                out["skipped"].append(
                    {
                        "company": c.name,
                        "reason": f"NO_STATE_MATCH province={province}",
                    }
                )
        rec = {
            "company": c.name,
            "vat": vat,
            "company_vals": vals_company,
            "partner_vals": {
                k: (p.state_id.browse(v).name if k == "state_id" else v)
                for k, v in vals_partner.items()
            },
        }
        if vals_company or vals_partner:
            if not DRY:
                if vals_company:
                    c.sudo().write(vals_company)
                if vals_partner:
                    p.sudo().write(vals_partner)
            rec["applied"] = not DRY
            out["writes"].append(rec)
        else:
            out["skipped"].append({"company": c.name, "reason": "ALREADY_SET"})
    if not DRY:
        env.cr.commit()
    Path(OUT).write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
