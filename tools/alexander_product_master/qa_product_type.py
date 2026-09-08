# ruff: noqa
"""Read-only product-type QA after apply."""

import json

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
T = env["product.template"].sudo().with_context(**ctx)

def _one(name):
    recs = T.search([("name", "=", name)])
    if len(recs) != 1:
        return None
    return recs[0]


grava = _one("Agregado grueso (grava) 3/4")
dup = T.search([("name", "=", "(AGREGADO GRUESO) GRAVA 3/4")])
svc = _one("Servicios profesionales")
physical_as_service = T.search(
    [
        ("type", "=", "service"),
        ("active", "=", True),
        "|",
        "|",
        "|",
        "|",
        ("name", "ilike", "grava"),
        ("name", "ilike", "arena lavada"),
        ("name", "ilike", "disco de corte"),
        ("name", "ilike", "pinza de corte"),
        ("name", "ilike", "agregado"),
    ]
)
# Exclude known remaining services that mention material in a service sense
physical_as_service = physical_as_service.filtered(
    lambda r: not any(
        k in (r.name or "").lower()
        for k in (
            "caliche",
            "servicio material",
            "transporte",
            "traslado",
            "bote ",
            "corte, carga",
            "corte y carga",
        )
    )
)

pinaria = T.search(
    ["|", ("company_id.name", "ilike", "pinaria"), ("company_id.name", "ilike", "piñaria")]
)
pinaria_as_service = pinaria.filtered(lambda r: r.type == "service")
catalog = T.search([("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")])
services = catalog.filtered(lambda r: r.type == "service")
purchase_false_physical = catalog.filtered(
    lambda r: r.type == "consu" and r.active and not r.purchase_ok
)
# Apertura histórica is the documented exception
purchase_false_physical = purchase_false_physical.filtered(
    lambda r: "apertura" not in (r.name or "").lower()
)

posted = env["account.move"].sudo().search_count(
    [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
)
grava_inv = 0
if grava:
    grava_inv = env["account.move.line"].sudo().search_count(
        [("product_id", "in", grava.product_variant_ids.ids)]
    )

errors = []
if not grava:
    errors.append("grava canonical missing")
else:
    if grava.type != "consu":
        errors.append(f"grava type={grava.type}")
    if "is_storable" in grava._fields and grava.is_storable:
        errors.append("grava is_storable")
    if not grava.sale_ok:
        errors.append("grava sale_ok False")
    if not grava.purchase_ok:
        errors.append("grava purchase_ok False")
if dup and dup.filtered("active"):
    errors.append("archived grava 138 reactivated")
if not svc or svc.type != "service":
    errors.append("servicios profesionales not service")
if svc and float(svc.list_price or 0) != 0:
    errors.append("servicios profesionales price")
if svc and "is_storable" in svc._fields and svc.is_storable:
    errors.append("servicios profesionales storable")
if pinaria_as_service:
    errors.append(f"pinaria as service: {pinaria_as_service.mapped('name')}")
if physical_as_service:
    errors.append(f"physical as service: {physical_as_service.mapped('name')}")
if purchase_false_physical:
    errors.append(
        f"physical purchase_ok false: {purchase_false_physical.mapped('name')[:20]}"
    )
if posted != 27:
    errors.append(f"posted invoices {posted}")

report = {
    "PRODUCTS_AUDITED": len(catalog),
    "SERVICE_COUNT": len(services),
    "SERVICE_NAMES": [r.name for r in services],
    "GRAVA_CANONICAL_PRODUCT_ID": grava.id if grava else None,
    "GRAVA_FINAL_TYPE": grava.type if grava else None,
    "GRAVA_FINAL_SALE_OK": bool(grava.sale_ok) if grava else None,
    "GRAVA_FINAL_PURCHASE_OK": bool(grava.purchase_ok) if grava else None,
    "GRAVA_IS_STORABLE": bool(grava.is_storable)
    if grava and "is_storable" in grava._fields
    else None,
    "GRAVA_INVOICE_LINES": grava_inv,
    "DUPLICATE_138_ACTIVE": bool(dup.filtered("active")) if dup else False,
    "SERVICIOS_PROFESIONALES_TYPE": svc.type if svc else None,
    "SERVICIOS_PROFESIONALES_PRICE": float(svc.list_price or 0) if svc else None,
    "PINARIA_PRODUCTS_AUDITED": len(pinaria),
    "PIÑARIA_PHYSICAL_PRODUCTS_AS_SERVICE": len(pinaria_as_service),
    "PHYSICAL_AS_SERVICE_REMAINING": [r.name for r in physical_as_service],
    "PHYSICAL_PURCHASE_OK_FALSE_REMAINING": [
        r.name for r in purchase_false_physical
    ],
    "POSTED_INVOICES": posted,
    "CRITICAL_ERRORS": len(errors),
    "HIGH_ERRORS": 0,
    "ERRORS": errors,
    "STATUS": "PASS" if not errors else "FAIL",
}
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
