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

# Clean leftover test docs
old_so = env["sale.order"].sudo().search([("client_order_ref", "=", TAG)])
old_po = env["purchase.order"].sudo().search([("partner_ref", "=", TAG)])
old_so.unlink()
old_po.filtered(lambda p: p.state in ("draft", "cancel")).unlink()

so = env["sale.order"].sudo().create(
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
so_ok = bool(so.order_line) and so.order_line[0].product_id.id == product.id
po = env["purchase.order"].sudo().create(
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
po_ok = bool(po.order_line) and po.order_line[0].product_id.id == product.id

moves_before = env["stock.move"].sudo().search_count([]) if "stock.move" in env else 0
quants_before = env["stock.quant"].sudo().search_count([]) if "stock.quant" in env else 0

# Confirm sale order only if product is not storable (no inventory policy).
confirmed = False
if so_ok and not grava.is_storable:
    so.action_confirm()
    confirmed = so.state in ("sale", "done")
    if not confirmed:
        errors.append(f"SO confirm state={so.state}")

moves_after = env["stock.move"].sudo().search_count([]) if "stock.move" in env else 0
quants_after = env["stock.quant"].sudo().search_count([]) if "stock.quant" in env else 0
stock_created = (moves_after - moves_before) + (quants_after - quants_before)
if stock_created:
    errors.append(f"stock created moves={moves_after - moves_before} quants={quants_after - quants_before}")

# Discard test documents
if so.state not in ("draft", "cancel"):
    try:
        so.with_context(disable_cancel_warning=True)._action_cancel()
    except Exception:
        so.action_cancel()
so.unlink()
if po.state in ("draft", "cancel"):
    po.unlink()

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
if not svc or svc.type != "service" or (svc.is_storable if "is_storable" in svc._fields else False):
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
