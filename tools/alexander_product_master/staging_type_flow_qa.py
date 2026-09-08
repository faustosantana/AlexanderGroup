# ruff: noqa
"""Staging-only: add Grava to a draft quotation and a draft PO, then discard.

Does not confirm deliveries or create opening stock. Unlinks the test docs.
"""

import json

GRAVA = "Agregado grueso (grava) 3/4"
TAG = "DXQA-PRODUCT-TYPE-AUDIT"

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
grava = (
    env["product.template"]
    .sudo()
    .with_context(**ctx)
    .search([("name", "=", GRAVA)], limit=1)
)
errors = []
if not grava:
    print(json.dumps({"STATUS": "FAIL", "ERRORS": ["grava missing"]}))
    raise SystemExit(0)

product = grava.product_variant_id
company = env["res.company"].sudo().search([], limit=1)
partner = env["res.partner"].sudo().search([("customer_rank", ">", 0)], limit=1)
if not partner:
    partner = env["res.partner"].sudo().search([], limit=1)
vendor = env["res.partner"].sudo().search([("supplier_rank", ">", 0)], limit=1)
if not vendor:
    vendor = partner


def _discard_orders(records, cancel_methods):
    for rec in records:
        if rec.state != "cancel":
            for meth in cancel_methods:
                if hasattr(rec, meth):
                    try:
                        getattr(rec, meth)()
                        break
                    except Exception:
                        continue
        if rec.state in ("draft", "cancel"):
            rec.unlink()


# Clean leftover test docs
old_so = env["sale.order"].sudo().search([("client_order_ref", "=", TAG)])
old_po = env["purchase.order"].sudo().search([("partner_ref", "=", TAG)])
_discard_orders(old_so, ("_action_cancel", "action_cancel"))
_discard_orders(old_po, ("button_cancel", "action_cancel"))

so = (
    env["sale.order"]
    .sudo()
    .create(
        {
            "partner_id": partner.id,
            "company_id": company.id,
            "client_order_ref": TAG,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": 1,
                        "price_unit": float(grava.list_price or 0),
                    },
                )
            ],
        }
    )
)
so_ok = bool(so.order_line) and so.order_line[0].product_id.id == product.id
po = (
    env["purchase.order"]
    .sudo()
    .create(
        {
            "partner_id": vendor.id,
            "company_id": company.id,
            "partner_ref": TAG,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_qty": 1,
                        "price_unit": float(grava.list_price or 0),
                    },
                )
            ],
        }
    )
)
po_ok = bool(po.order_line) and po.order_line[0].product_id.id == product.id

moves_before = env["stock.move"].sudo().search_count([]) if "stock.move" in env else 0
quants_before = (
    env["stock.quant"].sudo().search_count([]) if "stock.quant" in env else 0
)
# Do not confirm: Odoo 19 may create a delivery/move even for non-storable goods.
# Selection on draft SO/PO is the required future-use proof.
confirmed = False
moves_after = env["stock.move"].sudo().search_count([]) if "stock.move" in env else 0
quants_after = env["stock.quant"].sudo().search_count([]) if "stock.quant" in env else 0
stock_created = (moves_after - moves_before) + (quants_after - quants_before)
if stock_created:
    errors.append(
        f"stock created moves={moves_after - moves_before} quants={quants_after - quants_before}"
    )

# Discard test documents (cancel first — purchase forbids unlink in draft/purchase).
_discard_orders(so, ("_action_cancel", "action_cancel"))
_discard_orders(po, ("button_cancel", "button_draft"))

if not so_ok:
    errors.append("grava not selectable on quotation")
if not po_ok:
    errors.append("grava not selectable on purchase order")
if grava.type != "consu":
    errors.append(f"grava type {grava.type}")
if not grava.sale_ok or not grava.purchase_ok:
    errors.append("grava flags")

svc = (
    env["product.template"]
    .sudo()
    .with_context(**ctx)
    .search([("name", "=", "Servicios profesionales")], limit=1)
)
if (
    not svc
    or svc.type != "service"
    or (svc.is_storable if "is_storable" in svc._fields else False)
):
    errors.append("professional services type")

report = {
    "GRAVA_SALE_SELECTION": "PASS" if so_ok else "FAIL",
    "GRAVA_PURCHASE_SELECTION": "PASS" if po_ok else "FAIL",
    "GRAVA_SO_CONFIRMED": confirmed,
    "PROFESSIONAL_SERVICES_TYPE": svc.type if svc else None,
    "STOCK_CREATED": stock_created,
    "ERRORS": errors,
    "STATUS": "PASS" if not errors else "FAIL",
}
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
