# ruff: noqa
"""Apply Alexander product master via Odoo ORM.

Run inside odoo shell. Reads PRODUCT_MASTER_PAYLOAD JSON.
Never writes SQL to product tables. Never touches invoices, NCF, stock, or cost.
"""

import json
import os
import re
import unicodedata
from collections import Counter

PAYLOAD_PATH = os.environ.get(
    "PRODUCT_MASTER_PAYLOAD", "/tmp/product_master_payload.json"
)
DRY = os.environ.get("PRODUCT_MASTER_DRY", "0") == "1"
BATCH = os.environ.get("PRODUCT_MASTER_BATCH", "ALEXANDER_PRODUCT_MASTER_20260907")
PINARIA_NEEDLE = "PINARIA"


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _truthy(value) -> bool:
    return value in (True, 1, "1", "True", "true", "YES", "yes")


def _load():
    with open(PAYLOAD_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _pinaria(env):
    for c in env["res.company"].sudo().search([]):
        if PINARIA_NEEDLE in _fold(c.name).replace("ñ", "n").replace("naria", "naria"):
            if "pinaria" in _fold(c.name).replace("ñ", "n"):
                return c
    for c in env["res.company"].sudo().search([]):
        if "pinaria" in _fold(c.name) or "piñaria" in (c.name or "").lower():
            return c
    raise RuntimeError("Piñaria company not found")


def _category(env, name: str):
    Categ = env["product.category"].sudo()
    rec = Categ.search([("name", "=", name)], limit=1)
    if rec:
        return rec
    if DRY:
        return Categ.browse()
    return Categ.create({"name": name})


def _uom(env, name: str):
    Uom = env["uom.uom"].sudo()
    rec = Uom.search([("name", "=", name)], limit=1)
    if rec:
        return rec
    aliases = {
        "Units": ["Units", "Unit", "Units"],
        "Gal": ["Gal", "gal", "Galón"],
        "lb": ["lb", "lbs", "lb(s)"],
        "kg": ["kg"],
        "m²": ["m²", "m2"],
        "m³": ["m³", "m3"],
        "m": ["m"],
        "ft": ["ft", "ft."],
        "Hours": ["Hours", "Hour"],
        "Days": ["Days", "Day"],
    }
    for alias in aliases.get(name, [name]):
        rec = Uom.search([("name", "=", alias)], limit=1)
        if rec:
            return rec
    rec = Uom.search([("name", "ilike", name)], limit=1)
    return rec


def _find_existing(env, row: dict):
    Template = env["product.template"].sudo().with_context(active_test=False)
    trust_ids = os.environ.get("PRODUCT_MASTER_TRUST_IDS", "0") == "1"
    if (
        trust_ids
        and row.get("CURRENT_ODOO_PRODUCT_ID")
        and str(row["CURRENT_ODOO_PRODUCT_ID"]).isdigit()
    ):
        rec = Template.browse(int(row["CURRENT_ODOO_PRODUCT_ID"]))
        expected = _fold(row.get("CURRENT_ODOO_NAME") or "")
        if rec.exists() and (not expected or _fold(rec.name) == expected):
            return rec, "ID"
    name = row.get("CANONICAL_NAME") or ""
    if name:
        rec = Template.search([("name", "=ilike", name)], limit=2)
        if len(rec) == 1:
            return rec, "NAME"
    if _truthy(row.get("IS_SERVICE")):
        rec = Template.search([("name", "ilike", "Servicios profesionales")], limit=2)
        exact = rec.filtered(
            lambda t: _fold(t.name)
            in {"servicios profesionales", "servicio profesional"}
        )
        if exact:
            return exact[0], "SERVICE"
    return Template.browse(), None


def apply(env, rows: list[dict]) -> dict:
    report = Counter()
    actions = []
    pinaria = _pinaria(env)
    Template = env["product.template"].sudo()
    for row in rows:
        action = row.get("ACTION")
        if action in {"MANUAL_REVIEW", "IGNORE_ROW", ""}:
            report["SKIPPED_REVIEW"] += 1
            continue
        existing, how = _find_existing(env, row)
        vals = {}
        if action == "MAP_TO_SERVICIOS_PROFESIONALES" or _truthy(row.get("IS_SERVICE")):
            if existing:
                if float(existing.list_price or 0) != 0:
                    vals["list_price"] = 0.0
                if vals and not DRY:
                    existing.with_context(
                        tracking_disable=True, mail_notrack=True
                    ).write(vals)
                    report["PRODUCTS_UPDATED_PRICE"] += 1
                else:
                    report["PRODUCTS_REUSED"] += 1
                actions.append(
                    {
                        "name": existing.name,
                        "id": existing.id,
                        "action": "REUSE_SERVICE",
                        "how": how,
                    }
                )
            else:
                create_vals = {
                    "name": "Servicios profesionales",
                    "type": "service",
                    "sale_ok": True,
                    "purchase_ok": True,
                    "list_price": 0.0,
                    "company_id": False,
                    "categ_id": _category(env, "Servicios").id if not DRY else False,
                }
                if DRY:
                    report["PRODUCTS_CREATED"] += 1
                    actions.append(
                        {
                            "name": "Servicios profesionales",
                            "id": None,
                            "action": "CREATE_SERVICE",
                        }
                    )
                else:
                    rec = Template.with_context(
                        tracking_disable=True, mail_notrack=True
                    ).create(create_vals)
                    report["PRODUCTS_CREATED"] += 1
                    actions.append(
                        {"name": rec.name, "id": rec.id, "action": "CREATE_SERVICE"}
                    )
            continue

        final_price = row.get("FINAL_LIST_PRICE")
        if existing:
            report["PRODUCTS_REUSED"] += 1
            write_vals = {}
            if final_price not in ("", None):
                current = float(existing.list_price or 0)
                target = float(final_price)
                if target > current + 0.009:
                    write_vals["list_price"] = target
            if write_vals and not DRY:
                existing.with_context(tracking_disable=True, mail_notrack=True).write(
                    write_vals
                )
                report["PRODUCTS_UPDATED_PRICE"] += 1
            elif not write_vals:
                report["REUSE_NO_CHANGE"] += 1
            actions.append(
                {
                    "name": existing.name,
                    "id": existing.id,
                    "action": action,
                    "how": how,
                    "old": float(existing.list_price or 0),
                    "new": write_vals.get("list_price"),
                }
            )
            continue

        if action not in {"CREATE_SHARED_PRODUCT", "CREATE_PIÑARIA_PRODUCT"}:
            report["SKIPPED_UNKNOWN"] += 1
            continue
        if final_price in ("", None):
            report["SKIPPED_NO_PRICE"] += 1
            continue
        categ = _category(env, row.get("CATEGORY") or "Ferretería")
        uom = _uom(env, row.get("UOM") or "Units")
        create_vals = {
            "name": row["CANONICAL_NAME"],
            "type": "consu",
            "sale_ok": True,
            "purchase_ok": True,
            "list_price": float(final_price),
            "company_id": (
                pinaria.id if row.get("COMPANY_SCOPE") == "PINARIA" else False
            ),
            "description_sale": row.get("MAX_PRICE_DESCRIPTION") or False,
        }
        if categ:
            create_vals["categ_id"] = categ.id
        if uom:
            create_vals["uom_id"] = uom.id
            if "uom_po_id" in Template._fields:
                create_vals["uom_po_id"] = uom.id
        if DRY:
            report["PRODUCTS_CREATED"] += 1
            actions.append(
                {"name": row["CANONICAL_NAME"], "id": None, "action": action}
            )
        else:
            rec = Template.with_context(
                tracking_disable=True, mail_notrack=True
            ).create(create_vals)
            report["PRODUCTS_CREATED"] += 1
            actions.append({"name": rec.name, "id": rec.id, "action": action})

    env.cr.commit() if not DRY else None
    return {
        "BATCH": BATCH,
        "DRY": DRY,
        "counts": dict(report),
        "actions_sample": actions[:50],
        "actions_total": len(actions),
    }


payload = _load()
rows = payload.get("products") or payload
print(json.dumps(apply(env, rows), ensure_ascii=False, indent=2, default=str))
