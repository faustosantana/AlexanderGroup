# ruff: noqa
"""Apply deterministic/high-confidence product nature fixes via ORM.

Never writes SQL to product tables. Never rewrites historical documents.
Never creates stock quants or valuation layers. Never changes standard_price,
company_id, list_price, or active.
"""

import json
import os

DRY = os.environ.get("PRODUCT_TYPE_DRY", "0") == "1"
PAYLOAD_PATH = os.environ.get(
    "PRODUCT_TYPE_PAYLOAD", "/tmp/product_type_apply_payload.json"
)
BATCH = os.environ.get("PRODUCT_TYPE_BATCH", "ALEXANDER_PRODUCT_TYPE_20260908")


def _load():
    with open(PAYLOAD_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _find(env, row):
    Template = env["product.template"].sudo().with_context(active_test=False)
    name = row.get("NAME") or ""
    recs = Template.search([("name", "=", name)])
    if len(recs) == 1:
        return recs[0], "NAME"
    hint = row.get("TEMPLATE_ID")
    if hint:
        rec = Template.browse(int(hint))
        if rec.exists() and rec.name == name:
            return rec, "ID_NAME"
    return Template.browse(), None


def apply(env):
    data = _load()
    rows = data.get("rows") or []
    Template = env["product.template"].sudo().with_context(
        allowed_company_ids=env["res.company"].sudo().search([]).ids,
        active_test=False,
    )
    Move = env["stock.move"].sudo() if "stock.move" in env else None
    Quant = env["stock.quant"].sudo() if "stock.quant" in env else None
    AML = env["account.move.line"].sudo()
    stock_before = Move.search_count([]) if Move is not None else 0
    quant_before = Quant.search_count([]) if Quant is not None else 0
    posted_before = env["account.move"].sudo().search_count(
        [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
    )
    report = {
        "BATCH": BATCH,
        "DRY": DRY,
        "ROWS": len(rows),
        "WRITTEN": 0,
        "SKIPPED": 0,
        "MISSING": [],
        "CHANGED": [],
        "HISTORICAL_DOCUMENTS_CHANGED": 0,
        "STOCK_MOVES_CREATED": 0,
        "STOCK_QUANTS_CREATED": 0,
        "STANDARD_PRICE_CHANGED": 0,
        "NCF_CHANGED": 0,
        "CRITICAL_ERRORS": 0,
        "HIGH_ERRORS": 0,
    }
    for row in rows:
        rec, how = _find(env, row)
        if not rec:
            report["MISSING"].append(row.get("NAME"))
            report["SKIPPED"] += 1
            continue
        if not rec.active and row.get("ACTION") != "KEEP_ARCHIVED":
            # Never reactivate. Skip archived even if payload drifted.
            report["SKIPPED"] += 1
            continue
        old = {
            "type": rec.type,
            "sale_ok": bool(rec.sale_ok),
            "purchase_ok": bool(rec.purchase_ok),
            "is_storable": bool(rec.is_storable) if "is_storable" in rec._fields else None,
            "standard_price": float(rec.standard_price or 0),
            "company_id": rec.company_id.id or False,
            "list_price": float(rec.list_price or 0),
            "active": bool(rec.active),
        }
        aml_ids = AML.search([("product_id", "in", rec.product_variant_ids.ids)]).ids
        vals = {}
        proposed_type = row.get("PROPOSED_TYPE")
        if proposed_type and rec.type != proposed_type:
            vals["type"] = proposed_type
        if "is_storable" in rec._fields and proposed_type == "consu":
            if rec.is_storable:
                report["HIGH_ERRORS"] += 1
                report["SKIPPED"] += 1
                report["CHANGED"].append(
                    {"id": rec.id, "name": rec.name, "skipped": "storable"}
                )
                continue
            vals["is_storable"] = False
        if bool(row.get("PROPOSED_SALE_OK")) != bool(rec.sale_ok):
            vals["sale_ok"] = bool(row.get("PROPOSED_SALE_OK"))
        if bool(row.get("PROPOSED_PURCHASE_OK")) != bool(rec.purchase_ok):
            vals["purchase_ok"] = bool(row.get("PROPOSED_PURCHASE_OK"))
        if not vals:
            report["SKIPPED"] += 1
            continue
        if not DRY:
            rec.with_context(tracking_disable=True, mail_notrack=True).write(vals)
        rec.invalidate_recordset()
        new_cost = float(rec.standard_price or 0)
        if abs(new_cost - old["standard_price"]) > 1e-9:
            report["STANDARD_PRICE_CHANGED"] += 1
            report["HIGH_ERRORS"] += 1
        if (rec.company_id.id or False) != old["company_id"]:
            report["HIGH_ERRORS"] += 1
        if bool(rec.active) != old["active"]:
            report["CRITICAL_ERRORS"] += 1
        aml_after = AML.search([("product_id", "in", rec.product_variant_ids.ids)]).ids
        if aml_after != aml_ids:
            report["HISTORICAL_DOCUMENTS_CHANGED"] += 1
            report["CRITICAL_ERRORS"] += 1
        report["WRITTEN"] += 1
        report["CHANGED"].append(
            {
                "id": rec.id,
                "name": rec.name,
                "how": how,
                "old": old,
                "vals": vals,
            }
        )

    if not DRY:
        env.cr.commit()

    stock_after = Move.search_count([]) if Move is not None else 0
    quant_after = Quant.search_count([]) if Quant is not None else 0
    posted_after = env["account.move"].sudo().search_count(
        [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
    )
    report["STOCK_MOVES_CREATED"] = stock_after - stock_before
    report["STOCK_QUANTS_CREATED"] = quant_after - quant_before
    if report["STOCK_MOVES_CREATED"] or report["STOCK_QUANTS_CREATED"]:
        report["CRITICAL_ERRORS"] += 1
    if posted_after != posted_before:
        report["NCF_CHANGED"] = 1
        report["CRITICAL_ERRORS"] += 1
    if report["MISSING"]:
        report["HIGH_ERRORS"] += len(report["MISSING"])
    report["POSTED_INVOICES"] = posted_after
    report["STATUS"] = (
        "PASS"
        if report["CRITICAL_ERRORS"] == 0 and report["HIGH_ERRORS"] == 0
        else "FAIL"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return report


apply(env)
