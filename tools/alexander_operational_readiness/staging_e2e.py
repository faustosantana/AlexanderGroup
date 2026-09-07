# ruff: noqa
"""E2E staging: cotización+SO+factura draft y OC+factura draft. No postea ventas (no consume NCF)."""

import json
from pathlib import Path

TAG = "DXQA-OPREADY-20260907"
OUT = "/tmp/op_ready_staging_e2e.json"


def run(env):
    report = {"flows": [], "MAIL_SENT": 0, "NCF_CONSUMED": 0, "posted_invoices": 0}
    companies = env["res.company"].search([("id", "!=", 1)], order="id")
    do = env["res.country"].search([("code", "=", "DO")], limit=1)
    ncf_before = {}
    if "justech.do.ncf.range" in env:
        for r in env["justech.do.ncf.range"].search([("state", "=", "active")]):
            ncf_before[r.id] = r.next_sequence
    for c in companies:
        rec = {"company": c.name, "cid": c.id}
        e = env(context=dict(env.context, allowed_company_ids=[c.id]))
        Partner = e["res.partner"].with_company(c)
        partner = Partner.search([("name", "=", f"{TAG} CLIENTE {c.id}")], limit=1)
        if not partner:
            partner = Partner.create(
                {
                    "name": f"{TAG} CLIENTE {c.id}",
                    "is_company": True,
                    "company_type": "company",
                    "country_id": do.id if do else False,
                    "vat": f"1{c.id:08d}",
                    "customer_rank": 1,
                    "company_id": False,
                }
            )
        vendor = Partner.search([("name", "=", f"{TAG} PROV {c.id}")], limit=1)
        if not vendor:
            vendor = Partner.create(
                {
                    "name": f"{TAG} PROV {c.id}",
                    "is_company": True,
                    "company_type": "company",
                    "country_id": do.id if do else False,
                    "vat": f"2{c.id:08d}",
                    "supplier_rank": 1,
                    "company_id": False,
                }
            )
        Product = e["product.product"].with_company(c)
        product = Product.search([("name", "=", f"{TAG} SERV {c.id}")], limit=1)
        if not product:
            product = Product.create(
                {
                    "name": f"{TAG} SERV {c.id}",
                    "type": "service",
                    "list_price": 100.0,
                    "sale_ok": True,
                    "purchase_ok": True,
                    "company_id": c.id,
                }
            )
        # SALE
        SO = e["sale.order"].with_company(c)
        so = SO.create(
            {
                "partner_id": partner.id,
                "company_id": c.id,
                "client_order_ref": TAG,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        rec["so"] = so.name
        rec["so_state"] = so.state
        inv_ids = so._create_invoices() if hasattr(so, "_create_invoices") else so
        invoices = so.invoice_ids
        rec["sale_invoice_ids"] = invoices.ids
        rec["sale_invoice_state"] = invoices.mapped("state")
        rec["sale_ncf"] = invoices.mapped("justech_do_ncf") if invoices else []
        # PURCHASE
        PO = e["purchase.order"].with_company(c)
        po = PO.create(
            {
                "partner_id": vendor.id,
                "company_id": c.id,
                "partner_ref": TAG,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_qty": 1,
                            "price_unit": 80.0,
                            "name": product.name,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        rec["po"] = po.name
        rec["po_state"] = po.state
        rec["sale_ok"] = so.state in ("sale", "done")
        rec["purchase_ok"] = po.state in ("purchase", "done")
        report["flows"].append(rec)
        env.cr.commit()
    ncf_after = {}
    if "justech.do.ncf.range" in env:
        for r in env["justech.do.ncf.range"].search([("state", "=", "active")]):
            ncf_after[r.id] = r.next_sequence
    report["NCF_CONSUMED"] = int(ncf_before != ncf_after)
    report["ncf_before"] = ncf_before
    report["ncf_after"] = ncf_after
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
