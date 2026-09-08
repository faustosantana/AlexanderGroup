# ruff: noqa
"""Apply Alexander product master Phase 2 via ORM. No historical documents."""

import json
import os
import re
import unicodedata
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from odoo.tools.float_utils import float_round

PAYLOAD_PATH = os.environ.get("PHASE2_PAYLOAD", "/tmp/phase2_apply_payload.json")
DRY = os.environ.get("PHASE2_DRY", "0") == "1"
BATCH = os.environ.get("PHASE2_BATCH", "ALEXANDER_PRODUCT_PHASE2_20260908")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _money2(value) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _pinaria(env):
    for c in env["res.company"].sudo().search([]):
        if "pinaria" in _fold(c.name):
            return c
    raise RuntimeError("Piñaria company not found")


def _find(env, row):
    Template = env["product.template"].sudo().with_context(active_test=False)
    name = row.get("MATCHED_PRODUCT") or row.get("RAW_DESCRIPTION") or ""
    trust = os.environ.get("PHASE2_TRUST_IDS", "0") == "1"
    pid = row.get("MATCHED_PRODUCT_ID")
    if trust and pid not in ("", None) and str(pid).isdigit():
        rec = Template.browse(int(pid))
        if rec.exists() and _fold(rec.name) == _fold(name or rec.name):
            return rec
    if name:
        rec = Template.search([("name", "=ilike", name)], limit=2)
        if len(rec) == 1:
            return rec
    return Template.browse()


def apply(env, rows):
    report = Counter()
    actions = []
    Template = env["product.template"].sudo()
    pinaria = _pinaria(env)
    Categ = env["product.category"].sudo()

    # Ensure Servicios profesionales is 0.00
    svc = Template.search([("name", "=ilike", "Servicios profesionales")], limit=1)
    if svc and abs(float(svc.list_price or 0) - 0.0) > 1e-9:
        if not DRY:
            svc.with_context(tracking_disable=True, mail_notrack=True).write(
                {"list_price": 0.0}
            )
        report["SERVICIOS_PRICE_NORMALIZED"] += 1

    for row in rows:
        action = row.get("ACTION")
        if action in {"KEEP_MANUAL_REVIEW", "IGNORE_NON_PRODUCT", "MAP_TO_SERVICES"}:
            report[action] += 1
            continue
        proposed = row.get("PROPOSED_LIST_PRICE")
        if proposed in ("", None):
            report["SKIPPED_NO_PRICE"] += 1
            continue
        target = _money2(proposed)
        target = float_round(target, precision_digits=2)

        if action == "CREATE_PIÑARIA_PRODUCT":
            existing = _find(
                env, {**row, "MATCHED_PRODUCT": row.get("RAW_DESCRIPTION")}
            )
            if existing:
                report["PINARIA_ALREADY_EXISTS"] += 1
                continue
            categ = Categ.search(
                [
                    (
                        "name",
                        "=",
                        (
                            "Carnes"
                            if row.get("IS_MEAT") in (True, "True", "true")
                            else "Alimentos"
                        ),
                    )
                ],
                limit=1,
            )
            vals = {
                "name": row["RAW_DESCRIPTION"],
                "type": "consu",
                "sale_ok": True,
                "purchase_ok": True,
                "list_price": target,
                "company_id": pinaria.id,
            }
            if categ:
                vals["categ_id"] = categ.id
            if DRY:
                report["NEW_PIÑARIA_PRODUCTS_CREATED"] += 1
            else:
                rec = Template.with_context(
                    tracking_disable=True, mail_notrack=True
                ).create(vals)
                actions.append(
                    {"id": rec.id, "name": rec.name, "action": action, "price": target}
                )
                report["NEW_PIÑARIA_PRODUCTS_CREATED"] += 1
            continue

        rec = _find(env, row)
        if not rec:
            report["SKIPPED_NOT_FOUND"] += 1
            continue
        current = float(rec.list_price or 0)
        current2 = _money2(current)
        if action == "PRICE_PRECISION_FIX":
            if abs(current - target) < 1e-9 and not (
                Decimal(str(current))
                != Decimal(str(current)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ):
                report["PRECISION_ALREADY_OK"] += 1
                continue
            # rounding must not floor below commercial 2-dec value of current
            if target + 0.009 < current2 and abs(target - current2) > 0.009:
                report["BLOCKED_PRICE_DECREASE"] += 1
                continue
            if not DRY:
                rec.with_context(tracking_disable=True, mail_notrack=True).write(
                    {"list_price": target}
                )
            report["PRICE_EXCESS_PRECISION_FIXED"] += 1
            actions.append(
                {"id": rec.id, "name": rec.name, "old": current, "new": target}
            )
            continue
        if action == "RESOLVE_EXISTING_UPDATE_PRICE":
            if target <= current2 + 0.0001:
                report["RESOLVE_EXISTING_NO_CHANGE"] += 1
                continue
            if not DRY:
                rec.with_context(tracking_disable=True, mail_notrack=True).write(
                    {"list_price": target}
                )
            report["RESOLVE_EXISTING_UPDATE_PRICE"] += 1
            actions.append(
                {"id": rec.id, "name": rec.name, "old": current, "new": target}
            )
            continue
        if action == "RESOLVE_EXISTING_NO_CHANGE":
            report["RESOLVE_EXISTING_NO_CHANGE"] += 1
            continue
        report["SKIPPED_UNKNOWN"] += 1

    if not DRY:
        env.cr.commit()
    return {
        "BATCH": BATCH,
        "DRY": DRY,
        "counts": dict(report),
        "actions_sample": actions[:40],
        "actions_total": len(actions),
    }


payload = json.load(open(PAYLOAD_PATH, encoding="utf-8"))
rows = payload.get("rows") or payload
print(json.dumps(apply(env, rows), ensure_ascii=False, indent=2, default=str))
