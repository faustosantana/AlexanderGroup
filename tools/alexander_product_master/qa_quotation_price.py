# ruff: noqa
"""Controlled quotation price QA. Creates tagged TEST drafts only, then discards.

Never confirms. Never posts fiscal docs. Never writes product.list_price.
"""

import json
import os

TAG = os.environ.get("PRICE_QA_TAG", "DXQA-PRICE-AUDIT")
SALE_LOGIN = os.environ.get("PRICE_QA_SALE_LOGIN", "fausto@justech.do")

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
errors = []
T = env["product.template"].sudo().with_context(**ctx)


def _discard_orders(records):
    for rec in records:
        if rec.state != "cancel":
            for meth in ("_action_cancel", "action_cancel", "button_cancel"):
                if hasattr(rec, meth):
                    try:
                        getattr(rec, meth)()
                        break
                    except Exception:
                        continue
        if rec.state in ("draft", "cancel"):
            rec.unlink()


def _find(name):
    recs = T.search([("name", "=", name)])
    return recs[:1] if recs else T.browse()


grava = _find("Agregado grueso (grava) 3/4")
svc = _find("Servicios profesionales")
# service with price > 0 if present
svc_priced = T.search(
    [("type", "=", "service"), ("list_price", ">", 0), ("sale_ok", "=", True), ("active", "=", True)],
    limit=1,
)
zero = svc
partner = env["res.partner"].sudo().search([("customer_rank", ">", 0)], limit=1)
if not partner:
    partner = env["res.partner"].sudo().search([], limit=1)
company = env["res.company"].sudo().search([], limit=1)

# leftover cleanup
old = env["sale.order"].sudo().search(["|", ("client_order_ref", "=", TAG), ("origin", "=", TAG)])
_discard_orders(old)

sale_user = env["res.users"].sudo().search([("login", "=", SALE_LOGIN)], limit=1)
if not sale_user:
    sale_user = env.user

def _system_price(product, partner):
    pl = False
    if partner and "property_product_pricelist" in partner._fields:
        pl = partner.property_product_pricelist
    if pl:
        try:
            return float(pl._get_product_price(product, 1.0, partner))
        except Exception:
            try:
                return float(pl._compute_price_rule(product, 1.0, partner)[0])
            except Exception:
                pass
    tmpl = product.product_tmpl_id
    return float(tmpl.list_price or 0)


def _make_so(product, price=None, discount=0.0, suffix=""):
    vals = {
        "partner_id": partner.id,
        "company_id": company.id,
        "client_order_ref": TAG,
        "origin": TAG,
        "order_line": [
            (
                0,
                0,
                {
                    "product_id": product.id,
                    "product_uom_qty": 1,
                    **({"price_unit": price} if price is not None else {}),
                    **({"discount": discount} if discount else {}),
                },
            )
        ],
    }
    so = env["sale.order"].with_user(sale_user).sudo().create(vals)
    so.invalidate_recordset()
    return so


cases = {}
master_before = {}

if not grava:
    errors.append("grava missing")
else:
    product = grava.product_variant_id
    master_before["grava"] = float(grava.list_price or 0)
    expected = _system_price(product, partner)
    so1 = _make_so(product)
    loaded = float(so1.order_line[:1].price_unit or 0)
    cases["PRODUCT_PRICE_LOADS_IN_QUOTATION"] = (
        "PASS" if abs(loaded - expected) < 0.02 or abs(loaded - master_before["grava"]) < 0.02 else "FAIL"
    )
    if cases["PRODUCT_PRICE_LOADS_IN_QUOTATION"] == "FAIL":
        errors.append(f"grava loaded {loaded} expected {expected} master {master_before['grava']}")

    # edit price
    manual = round(master_before["grava"] + 123.45, 2)
    try:
        so1.order_line[:1].with_user(sale_user).write({"price_unit": manual})
        cases["SALE_USER_CAN_EDIT_UNIT_PRICE"] = "PASS"
    except Exception as exc:
        cases["SALE_USER_CAN_EDIT_UNIT_PRICE"] = "FAIL"
        errors.append(f"edit blocked: {exc}")
    so1.invalidate_recordset()
    persisted = float(so1.order_line[:1].price_unit or 0)
    cases["EDITED_PRICE_PERSISTS_IN_QUOTATION"] = (
        "PASS" if abs(persisted - manual) < 0.02 else "FAIL"
    )
    grava.invalidate_recordset()
    master_after = float(grava.list_price or 0)
    cost_after = float(grava.standard_price or 0)
    cases["EDITING_QUOTATION_PRICE_DOES_NOT_CHANGE_PRODUCT_MASTER"] = (
        "PASS" if abs(master_after - master_before["grava"]) < 1e-9 else "FAIL"
    )
    if abs(master_after - master_before["grava"]) > 1e-9:
        cases["EDITING_QUOTATION_PRICE_DOES_NOT_CHANGE_PRODUCT_MASTER"] = "FAIL"
        errors.append(f"list_price changed {master_before['grava']} -> {master_after}")

    so2 = _make_so(product)
    loaded2 = float(so2.order_line[:1].price_unit or 0)
    cases["NEW_QUOTATION_RELOADS_SYSTEM_PRICE"] = (
        "PASS"
        if abs(loaded2 - expected) < 0.02 or abs(loaded2 - master_before["grava"]) < 0.02
        else "FAIL"
    )
    if abs(loaded2 - manual) < 0.02 and abs(manual - master_before["grava"]) > 1:
        cases["NEW_QUOTATION_RELOADS_SYSTEM_PRICE"] = "FAIL"
        errors.append(f"second quote reused manual {loaded2}")

    cases["grava"] = {
        "master": master_before["grava"],
        "system": expected,
        "first_loaded": loaded,
        "manual": manual,
        "persisted": persisted,
        "second_loaded": loaded2,
        "so1": so1.name,
        "so2": so2.name,
    }

    # discount on a third draft
    so3 = _make_so(product, discount=10.0)
    cases["DISCOUNT_LINE"] = {
        "price_unit": float(so3.order_line[:1].price_unit or 0),
        "discount": float(so3.order_line[:1].discount or 0),
        "subtotal": float(so3.order_line[:1].price_subtotal or 0),
    }

    # zero-price service
    if zero:
        soz = _make_so(zero.product_variant_id)
        cases["ZERO_PRICE_PRODUCT"] = {
            "name": zero.name,
            "master": float(zero.list_price or 0),
            "loaded": float(soz.order_line[:1].price_unit or 0),
        }

    if svc_priced and svc_priced.id != (zero.id if zero else 0):
        sos = _make_so(svc_priced.product_variant_id)
        cases["PRICED_SERVICE"] = {
            "name": svc_priced.name,
            "master": float(svc_priced.list_price or 0),
            "loaded": float(sos.order_line[:1].price_unit or 0),
        }

    # no-history product: first consu with price and no so/invoice if easy
    # audit log
    audit = {"available": False}
    if "justech.audit.log" in env:
        logs = env["justech.audit.log"].sudo().search(
            [
                ("model_name", "in", ["sale.order", "sale.order.line"]),
                ("record_id", "in", [so1.id] + so1.order_line.ids),
            ],
            limit=10,
            order="id desc",
        )
        audit = {
            "available": True,
            "model": "justech.audit.log",
            "count": len(logs),
            "sample": [
                {
                    "operation": l.operation_type,
                    "field": l.field_name,
                    "old": (l.old_value or "")[:80],
                    "new": (l.new_value or "")[:80],
                    "user": l.user_id.login if l.user_id else "",
                    "date": str(l.change_date),
                }
                for l in logs
            ],
        }
    cases["PRICE_CHANGE_AUDIT"] = audit

    # mail tracking on sale.order.line price_unit
    tracking = False
    if "mail.tracking.value" in env:
        tracking = (
            env["mail.tracking.value"].sudo().search_count(
                [
                    ("field_id.name", "=", "price_unit"),
                    ("mail_message_id.model", "=", "sale.order"),
                ]
            )
            > 0
            or env["mail.tracking.value"].sudo().search_count(
                [("mail_message_id.res_id", "=", so1.id)]
            )
            > 0
        )
    cases["MAIL_TRACKING_SEEN"] = tracking

# discard all tagged
created = env["sale.order"].sudo().search(["|", ("client_order_ref", "=", TAG), ("origin", "=", TAG)])
_discard_orders(created)
left = env["sale.order"].sudo().search_count(["|", ("client_order_ref", "=", TAG), ("origin", "=", TAG)])
if left:
    errors.append(f"test quotations leftover={left}")

# product master still unchanged
if grava:
    grava.invalidate_recordset()
    if abs(float(grava.list_price or 0) - master_before.get("grava", 0)) > 1e-9:
        errors.append("grava list_price changed after QA cleanup")

stock_created = 0
if "stock.move" in env:
    stock_created = env["stock.move"].sudo().search_count([("origin", "=", TAG)])

posted = env["account.move"].sudo().search_count(
    [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
)

required = [
    "PRODUCT_PRICE_LOADS_IN_QUOTATION",
    "SALE_USER_CAN_EDIT_UNIT_PRICE",
    "EDITED_PRICE_PERSISTS_IN_QUOTATION",
    "EDITING_QUOTATION_PRICE_DOES_NOT_CHANGE_PRODUCT_MASTER",
    "NEW_QUOTATION_RELOADS_SYSTEM_PRICE",
]
for key in required:
    if cases.get(key) != "PASS":
        if key not in cases:
            cases[key] = "FAIL"
            errors.append(f"missing {key}")

report = {
    "SALE_USER": sale_user.login,
    "CASES": cases,
    "STOCK_MOVES_CREATED": stock_created,
    "POSTED_INVOICES": posted,
    "ERRORS": errors,
    "PRODUCT_PRICE_LOADS_IN_QUOTATION": cases.get("PRODUCT_PRICE_LOADS_IN_QUOTATION"),
    "SALE_USER_CAN_EDIT_UNIT_PRICE": cases.get("SALE_USER_CAN_EDIT_UNIT_PRICE"),
    "EDITED_PRICE_PERSISTS_IN_QUOTATION": cases.get("EDITED_PRICE_PERSISTS_IN_QUOTATION"),
    "EDITING_QUOTATION_PRICE_DOES_NOT_CHANGE_PRODUCT_MASTER": cases.get(
        "EDITING_QUOTATION_PRICE_DOES_NOT_CHANGE_PRODUCT_MASTER"
    ),
    "NEW_QUOTATION_RELOADS_SYSTEM_PRICE": cases.get("NEW_QUOTATION_RELOADS_SYSTEM_PRICE"),
    "PRICE_CHANGE_AUDIT_AVAILABLE": (
        "YES" if cases.get("PRICE_CHANGE_AUDIT", {}).get("available") else "NO"
    ),
    "STATUS": "PASS" if not errors else "FAIL",
}
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
