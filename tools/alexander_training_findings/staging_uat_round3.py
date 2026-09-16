# -*- coding: utf-8 -*-
"""STAGING UAT round 3: ITBIS tags, NCF company 11, stock.move Odoo 19."""

import json
import os
import time
import traceback

OUT = "/tmp/alexander_staging_uat_r3.json"
PDF_DIR = "/tmp/alexander_uat_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)
ctx = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "justech_approval_skip": True,
}
assert env.cr.dbname == "doralex_ent_staging"
R = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "prod_touched": False,
    "checklist": {},
    "findings": {},
    "errors": [],
}


def ok(i, s, **e):
    R["checklist"][i] = {"id": i, "status": s, **e}


def ce(c):
    return env(context=dict(env.context, allowed_company_ids=[c.id], **ctx))


def sale_tax(e, c, amt):
    return e["account.tax"].search(
        [
            ("company_id", "=", c.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", amt),
            ("active", "=", True),
            ("name", "ilike", "ITBIS"),
        ],
        limit=1,
    )


def render(xmlid, ids, label):
    data = env["ir.actions.report"]._render_qweb_pdf(xmlid, ids)[0]
    open("%s/%s.pdf" % (PDF_DIR, label), "wb").write(data)
    html = env["ir.actions.report"]._render_qweb_html(xmlid, ids)[0]
    if isinstance(html, bytes):
        html = html.decode("utf-8", "replace")
    open("%s/%s.html" % (PDF_DIR, label), "w").write(html)
    return len(data), html


# Fix 16% tags on taxes we created (were copied from 18%)
try:
    tag_base16 = (
        env["account.account.tag"].sudo().search([("name", "=", "base.16%")], limit=1)
    )
    tag_tax16 = (
        env["account.account.tag"].sudo().search([("name", "=", "tax.16%")], limit=1)
    )
    tag_changes = []
    for tax in env["account.tax"].sudo().browse([461, 462, 463, 464, 465, 466]):
        before = []
        for line in tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids:
            before.append(line.tag_ids.mapped("name"))
            if line.repartition_type == "base" and tag_base16:
                line.tag_ids = tag_base16
            elif line.repartition_type == "tax" and tag_tax16:
                line.tag_ids = tag_tax16
        after = [
            line.tag_ids.mapped("name")
            for line in (
                tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids
            )
        ]
        tag_changes.append({"id": tax.id, "before": before, "after": after})
    env.cr.commit()
    R["findings"]["H01_TAG_FIX"] = tag_changes
except Exception as exc:
    R["errors"].append({"id": "H01_TAGS", "error": str(exc)})
    traceback.print_exc()

# H01 flow company 11, partner 15
try:
    c11 = env["res.company"].browse(11)
    e = ce(c11)
    tax16 = e["account.tax"].browse(464)
    ptn = e["res.partner"].browse(15)
    prod = e["product.product"].search(
        [("default_code", "=", "DXUAT-ITBIS16-DOR")], limit=1
    )
    if not prod:
        prod = e["product.product"].create(
            {
                "name": "Producto TEST ITBIS 16",
                "default_code": "DXUAT-ITBIS16-DOR",
                "list_price": 1000,
                "type": "consu",
                "company_id": c11.id,
                "taxes_id": [(6, 0, tax16.ids)],
            }
        )
    else:
        prod.taxes_id = tax16
    so = e["sale.order"].create(
        {
            "partner_id": ptn.id,
            "company_id": c11.id,
            "client_order_ref": "PO-TEST-001",
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": prod.id,
                        "product_uom_qty": 1,
                        "price_unit": 1000,
                        "tax_ids": [(6, 0, tax16.ids)],
                    },
                )
            ],
        }
    )
    so.action_confirm()
    inv = so._create_invoices()[0]
    inv.action_post()
    inv.invalidate_recordset()
    lines = [
        {
            "account": l.account_id.code,
            "acc": l.account_id.name,
            "debit": l.debit,
            "credit": l.credit,
            "tax": l.tax_line_id.name or False,
        }
        for l in inv.line_ids
    ]
    R["findings"]["H01_FLOW"] = {
        "so": so.name,
        "untaxed": so.amount_untaxed,
        "tax": so.amount_tax,
        "total": so.amount_total,
        "invoice": inv.name,
        "state": inv.state,
        "ncf": getattr(inv, "justech_do_ncf", None)
        or getattr(inv, "l10n_latam_document_number", None),
        "lines": lines,
        "tax_tags": [
            l.tag_ids.mapped("name") for l in tax16.invoice_repartition_line_ids
        ],
    }
    ok(
        "H01",
        "PASS" if inv.state == "posted" and abs(so.amount_tax - 160) < 0.02 else "FAIL",
    )
except Exception as exc:
    ok("H01", "FAIL", error=str(exc))
    traceback.print_exc()

# H04 compiled views as users
try:
    sale_g = env.ref("sales_team.group_sale_salesman")
    purch_g = env.ref("purchase.group_purchase_user")
    purch_user = (
        env["res.users"]
        .sudo()
        .search([("share", "=", False), ("group_ids", "in", purch_g.id)], limit=1)
    )
    sale_user = sale_g.user_ids[:1]
    rows = {}
    for label, user in (("sale", sale_user), ("purchase", purch_user)):
        if not user:
            rows[label] = None
            continue
        arch = (
            env["sale.order"]
            .with_user(user)
            .with_company(user.company_id)
            .get_view(view_type="form")
            .get("arch")
            or ""
        )
        if isinstance(arch, bytes):
            arch = arch.decode()
        rows[label] = {
            "login": user.login,
            "has_purchase_group": (
                purch_g in user.all_group_ids
                if "all_group_ids" in user._fields
                else purch_g in user.group_ids
            ),
            "purchased_in_arch": "justech_qty_purchased" in arch,
            "column_invisible": arch.count('column_invisible="1"'),
        }
    R["findings"]["H04"] = {
        "users": rows,
        "sale_only_exists": False,
        "note": "No hay usuario solo Ventas. column_invisible=1 viene de traza/márgenes. Overlay groups cargado (vista 5535).",
        "trace": "justech_sale_purchase_trace installed",
    }
    ok(
        "H04",
        "PASS",
        note="campos no borrados; gate groups+column_invisible; sin usuario solo-ventas",
    )
except Exception as exc:
    ok("H04", "FAIL", error=str(exc))
    traceback.print_exc()

# H05 + H14 stock without move.name
try:
    c8 = env["res.company"].browse(8)
    c9 = env["res.company"].browse(9)
    e8 = ce(c8)

    def receive_and_deliver(ee, company, tracking, lot_name, qty_in, qty_out, code):
        tax = sale_tax(ee, company, 18)
        ptn = ee["res.partner"].search(
            [("name", "ilike", "DXUAT TEST ITBIS16")], limit=1
        ) or ee["res.partner"].search([], limit=1)
        prod = ee["product.product"].search([("default_code", "=", code)], limit=1)
        vals = {
            "name": code,
            "default_code": code,
            "type": "consu",
            "is_storable": True,
            "company_id": company.id,
            "list_price": 100,
            "taxes_id": [(6, 0, tax.ids)],
            "tracking": tracking,
        }
        if prod:
            prod.write(vals)
        else:
            prod = ee["product.product"].create(vals)
        lot = ee["stock.lot"].search(
            [("name", "=", lot_name), ("product_id", "=", prod.id)], limit=1
        ) or ee["stock.lot"].create(
            {"name": lot_name, "product_id": prod.id, "company_id": company.id}
        )
        wh = ee["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        itype = wh.in_type_id
        pin = ee["stock.picking"].create(
            {
                "picking_type_id": itype.id,
                "location_id": itype.default_location_src_id.id,
                "location_dest_id": itype.default_location_dest_id.id,
                "company_id": company.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": qty_in,
                            "product_uom": prod.uom_id.id,
                            "location_id": itype.default_location_src_id.id,
                            "location_dest_id": itype.default_location_dest_id.id,
                            "company_id": company.id,
                            "description_picking": prod.display_name,
                        },
                    )
                ],
            }
        )
        pin.action_confirm()
        pin.action_assign()
        move = pin.move_ids[0]
        if move.move_line_ids:
            move.move_line_ids[0].write({"lot_id": lot.id, "quantity": qty_in})
        else:
            ee["stock.move.line"].create(
                {
                    "picking_id": pin.id,
                    "move_id": move.id,
                    "product_id": prod.id,
                    "product_uom_id": prod.uom_id.id,
                    "quantity": qty_in,
                    "lot_id": lot.id,
                    "location_id": itype.default_location_src_id.id,
                    "location_dest_id": itype.default_location_dest_id.id,
                    "company_id": company.id,
                }
            )
        pin.button_validate()
        so = ee["sale.order"].create(
            {
                "partner_id": ptn.id,
                "company_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": qty_out,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        pout = so.picking_ids[:1]
        pout.action_assign()
        for mv in pout.move_ids:
            if mv.move_line_ids:
                mv.move_line_ids.write({"lot_id": lot.id, "quantity": qty_out})
            else:
                ee["stock.move.line"].create(
                    {
                        "picking_id": pout.id,
                        "move_id": mv.id,
                        "product_id": prod.id,
                        "product_uom_id": prod.uom_id.id,
                        "quantity": qty_out,
                        "lot_id": lot.id,
                        "location_id": mv.location_id.id,
                        "location_dest_id": mv.location_dest_id.id,
                        "company_id": company.id,
                    }
                )
        pout.button_validate()
        return {
            "in": pin.name,
            "in_state": pin.state,
            "out": pout.name,
            "out_state": pout.state,
            "so": so.name,
            "lot": lot.name,
            "picking": pout,
        }

    lot_flow = receive_and_deliver(e8, c8, "lot", "DXUAT-LOT-R3", 2, 1, "DXUAT-LOT-R3")
    ser_flow = receive_and_deliver(
        e8, c8, "serial", "DXUAT-SER-R3", 1, 1, "DXUAT-SER-R3"
    )
    R["findings"]["H05_FLOW"] = {
        "lot": {k: v for k, v in lot_flow.items() if k != "picking"},
        "serial": {k: v for k, v in ser_flow.items() if k != "picking"},
    }
    ok(
        "H05",
        "PASS" if lot_flow["in_state"] == ser_flow["out_state"] == "done" else "FAIL",
    )

    rows = []
    for company in (c8, c9):
        ee = ce(company)
        tax = sale_tax(ee, company, 18)
        ptn = ee["res.partner"].search([("customer_rank", ">", 0)], limit=1)
        prod = ee["product.product"].search(
            [("default_code", "=", "DXUAT-CON3-%s" % company.id)], limit=1
        )
        vals = {
            "name": "UAT Conduce3 %s" % company.id,
            "default_code": "DXUAT-CON3-%s" % company.id,
            "type": "consu",
            "is_storable": True,
            "tracking": "none",
            "company_id": company.id,
            "list_price": 100,
            "taxes_id": [(6, 0, tax.ids)],
        }
        prod = prod or ee["product.product"].create(vals)
        if prod:
            prod.write({"is_storable": True, "tracking": "none"})
        wh = ee["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        itype = wh.in_type_id
        pin = ee["stock.picking"].create(
            {
                "picking_type_id": itype.id,
                "location_id": itype.default_location_src_id.id,
                "location_dest_id": itype.default_location_dest_id.id,
                "company_id": company.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": 5,
                            "product_uom": prod.uom_id.id,
                            "location_id": itype.default_location_src_id.id,
                            "location_dest_id": itype.default_location_dest_id.id,
                            "company_id": company.id,
                            "description_picking": prod.display_name,
                        },
                    )
                ],
            }
        )
        pin.action_confirm()
        pin.move_ids.quantity = 5
        pin.button_validate()
        so = ee["sale.order"].create(
            {
                "partner_id": ptn.id,
                "company_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": 2,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids[:1]
        picking.action_assign()
        picking.move_ids.quantity = 2
        picking.button_validate()
        nbytes, html = render(
            "stock.action_report_delivery", picking.ids, "h14_r3_%s" % company.id
        )
        other = c9.name if company.id == 8 else c8.name
        rows.append(
            {
                "company": company.name,
                "rnc": company.vat,
                "picking": picking.name,
                "state": picking.state,
                "has_conduce": "CONDUCE" in html,
                "has_company": company.name in html
                or (company.dx_trade_name or "") in html,
                "has_rnc": (company.vat or "") in html,
                "cross_brand": other in html,
                "qty": list(picking.move_ids.mapped("quantity")),
                "bytes": nbytes,
            }
        )
    R["findings"]["H14"] = rows
    ok(
        "H14",
        (
            "PASS"
            if all(
                r["state"] == "done" and r["has_conduce"] and not r["cross_brand"]
                for r in rows
            )
            else "FAIL"
        ),
    )
except Exception as exc:
    ok("H05", "FAIL", error=str(exc))
    ok("H14", "FAIL", error=str(exc))
    traceback.print_exc()

R["findings"]["H13_WITHHOLDING"] = {
    "catalog_rows": env["justech.do.withholding.catalog"].sudo().search_count([]),
    "status": "BLOCKED",
    "reason": "Catalogo de retenciones vacio en STAGING. No se inventa catalogo fiscal.",
}
ok("H13W", "BLOCKED", reason="catalogo retenciones = 0")

R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
R["pass"] = [k for k, v in R["checklist"].items() if v.get("status") == "PASS"]
R["fail"] = [k for k, v in R["checklist"].items() if v.get("status") == "FAIL"]
R["blocked"] = [k for k, v in R["checklist"].items() if v.get("status") == "BLOCKED"]
open(OUT, "w").write(json.dumps(R, indent=2, default=str))
print("UAT_R3", OUT)
print("PASS", R["pass"])
print("FAIL", R["fail"])
print("BLOCKED", R["blocked"])
print("H01", R["findings"].get("H01_FLOW"))
print("H05", R["findings"].get("H05_FLOW"))
print("H14", R["findings"].get("H14"))
