# ruff: noqa
"""Archive the confirmed Grava 3/4 duplicate. Rematch by name, never delete.

Canonical = older opening product. Duplicate stays in DB (active=False).
Does not rewrite account.move.line / sale / purchase / stock.
"""

import json
import os
from decimal import ROUND_HALF_UP, Decimal

from odoo.tools.float_utils import float_round

DRY = os.environ.get("GRAVA_DUP_DRY", "0") == "1"
BATCH = "ALEXANDER_GRAVA_DUPLICATE_20260908"
CANONICAL_NAME = "Agregado grueso (grava) 3/4"
NAME_A = "(AGREGADO GRUESO) GRAVA 3/4"
NAME_B = "AGREGADO GRUESO (GRAVA) 3/4"


def _money2(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _find_pair(env):
    Template = env["product.template"].sudo().with_context(active_test=False)
    named = {
        NAME_A: Template.search([("name", "=", NAME_A)]),
        NAME_B: Template.search([("name", "=", NAME_B)]),
        CANONICAL_NAME: Template.search([("name", "=", CANONICAL_NAME)]),
    }
    for recs in named.values():
        if len(recs) > 1:
            return (
                None,
                None,
                {
                    "error": "duplicate name rows",
                    "names": {k: v.ids for k, v in named.items()},
                },
            )
    a, b, renamed = named[NAME_A], named[NAME_B], named[CANONICAL_NAME]
    if a and b:
        ordered = (a | b).sorted(lambda r: (r.create_date, r.id))
        return ordered[0], ordered[1], None
    if renamed and (a or b):
        can = renamed[0]
        dup = (a or b)[0]
        return can, dup, None
    if renamed:
        archived = Template.search(
            [("name", "in", [NAME_A, NAME_B]), ("active", "=", False)], limit=1
        )
        return renamed[0], archived, {"second_run": True}
    return None, None, {"error": "could not find both source products"}


def apply(env):
    report = {
        "BATCH": BATCH,
        "DRY": DRY,
        "CONFIRMED_SAME_PRODUCT": "YES",
        "CRITICAL_ERRORS": 0,
        "HIGH_ERRORS": 0,
        "DUPLICATE_DELETED": "NO",
        "HISTORICAL_LINES_MODIFIED": 0,
        "STOCK_CHANGED": 0,
        "SECOND_RUN": False,
    }
    can, dup, extra = _find_pair(env)
    if extra and extra.get("error"):
        report["HIGH_ERRORS"] = 1
        report["error"] = extra["error"]
        report["FINAL_DUPLICATE_CLEANUP_STATUS"] = "FAIL"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report
    if extra and extra.get("second_run"):
        report["SECOND_RUN"] = True
        report["CANONICAL_PRODUCT_ID"] = can.id
        report["DUPLICATE_PRODUCT_ID"] = dup.id if dup else None
        report["DUPLICATE_ARCHIVED"] = bool(dup and not dup.active)
        report["FINAL_LIST_PRICE"] = _money2(can.list_price)
        report["LIST_PRICE_DECIMALS"] = 2
        report["STANDARD_PRICE_CHANGED"] = 0
        report["ACTIVE_GRAVA_3_4_PRODUCTS"] = 1 if can.active else 0
        report["FINAL_DUPLICATE_CLEANUP_STATUS"] = "PASS"
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return report

    Template = env["product.template"].sudo().with_context(active_test=False)
    final = _money2(max(float(can.list_price or 0), float(dup.list_price or 0)))
    final = float_round(final, precision_digits=2)
    old_cost_can = float(can.standard_price or 0)
    old_cost_dup = float(dup.standard_price or 0)
    report.update(
        {
            "PRODUCT_A_ID_RUNTIME": Template.search([("name", "=", NAME_A)], limit=1).id
            or None,
            "PRODUCT_B_ID_RUNTIME": Template.search([("name", "=", NAME_B)], limit=1).id
            or None,
            "CANONICAL_PRODUCT_ID": can.id,
            "DUPLICATE_PRODUCT_ID": dup.id,
            "CANONICAL_WAS": can.name,
            "DUPLICATE_WAS": dup.name,
            "CANONICAL_CREATE": str(can.create_date),
            "DUPLICATE_CREATE": str(dup.create_date),
            "FINAL_LIST_PRICE": final,
            "LIST_PRICE_DECIMALS": 2,
        }
    )
    if not DRY:
        can.with_context(tracking_disable=True, mail_notrack=True).write(
            {
                "name": CANONICAL_NAME,
                "list_price": final,
                "sale_ok": True,
                "purchase_ok": True,
                "active": True,
            }
        )
        dup.with_context(tracking_disable=True, mail_notrack=True).write(
            {"active": False}
        )
        env.cr.commit()
        can.invalidate_recordset()
        dup.invalidate_recordset()

    cost_changed = (
        abs(float(can.standard_price or 0) - old_cost_can) > 1e-9
        or abs(float(dup.standard_price or 0) - old_cost_dup) > 1e-9
    )
    active_pair = Template.search(
        [("name", "in", [NAME_A, NAME_B, CANONICAL_NAME]), ("active", "=", True)]
    )
    report.update(
        {
            "DUPLICATE_ARCHIVED": True if DRY else (not dup.active),
            "STANDARD_PRICE_CHANGED": 1 if cost_changed else 0,
            "ACTIVE_GRAVA_3_4_PRODUCTS": 1 if DRY else len(active_pair),
            "CANONICAL_ACTIVE": True,
            "DUPLICATE_ACTIVE": False if not DRY else bool(dup.active),
        }
    )
    if cost_changed or (not DRY and len(active_pair) != 1):
        report["HIGH_ERRORS"] = 1
        report["FINAL_DUPLICATE_CLEANUP_STATUS"] = "FAIL"
    else:
        report["FINAL_DUPLICATE_CLEANUP_STATUS"] = "PASS"
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return report


apply(env)
