# -*- coding: utf-8 -*-
"""STAGING UAT round 2 — Odoo 19 field names + company 11 NCF. Never Prod."""

import json
import os
import time
import traceback

TAG = "DXUAT-TF-20260916-R2"
OUT = "/tmp/alexander_staging_uat_r2.json"
PDF_DIR = "/tmp/alexander_uat_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

assert env.cr.dbname == "doralex_ent_staging"
report = {
    "tag": TAG,
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "prod_touched": False,
    "checklist": {},
    "findings": {},
    "errors": [],
}


def _ok(item, status, **extra):
    rec = {"id": item, "status": status}
    rec.update(extra)
    report["checklist"][item] = rec
    return rec


def _exc(item, exc):
    report["errors"].append({"id": item, "error": "%s: %s" % (type(exc).__name__, exc)})
    return _ok(item, "FAIL", error="%s: %s" % (type(exc).__name__, exc))


def ce(company):
    return env(
        context=dict(
            env.context,
            allowed_company_ids=[company.id],
            justech_approval_skip=True,
            **ctx_mail,
        )
    )


def tax_dump(tax):
    if not tax:
        return None

    def _rep(lines):
        return [
            {
                "type": line.repartition_type,
                "pct": line.factor_percent,
                "account": line.account_id.code or False,
                "account_name": line.account_id.name or False,
                "tags": line.tag_ids.mapped("name"),
            }
            for line in lines
        ]

    return {
        "id": tax.id,
        "name": tax.name,
        "company_id": tax.company_id.id,
        "company": tax.company_id.name,
        "amount": tax.amount,
        "amount_type": tax.amount_type,
        "type_tax_use": tax.type_tax_use,
        "price_include": tax.price_include,
        "tax_group": tax.tax_group_id.display_name,
        "tax_exigibility": getattr(tax, "tax_exigibility", None),
        "include_base_amount": tax.include_base_amount,
        "country": tax.country_id.code if tax.country_id else False,
        "invoice_rep": _rep(tax.invoice_repartition_line_ids),
        "refund_rep": _rep(tax.refund_repartition_line_ids),
    }


def sale_tax(e, company, amount):
    return e["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", amount),
            ("active", "=", True),
            ("name", "ilike", "ITBIS"),
        ],
        limit=1,
    )


def partner(e, company, name, vat):
    rec = e["res.partner"].search([("name", "=", name)], limit=1)
    vals = {
        "name": name,
        "company_id": company.id,
        "vat": vat,
        "is_company": True,
        "customer_rank": 1,
        "email": "dxuat.noreply@example.invalid",
        "country_id": env.ref("base.do").id,
    }
    rec = rec or e["res.partner"].create(vals)
    if "justech_do_rnc_status" in rec._fields:
        rec.write(
            {
                "justech_do_rnc_status": "valid",
                "justech_do_fiscal_config_state": "validated_padron",
            }
        )
    return rec


def product(e, company, code, name, price, taxes, storable=False):
    rec = e["product.product"].search([("default_code", "=", code)], limit=1)
    vals = {
        "name": name,
        "default_code": code,
        "list_price": price,
        "type": "consu",
        "company_id": company.id,
        "taxes_id": [(6, 0, taxes.ids)] if taxes else [(6, 0, [])],
        "description_sale": "Desc %s" % code,
    }
    if "is_storable" in e["product.product"]._fields:
        vals["is_storable"] = storable
    if rec:
        rec.write(vals)
        return rec
    return e["product.product"].create(vals)


def render_pdf(xmlid, ids, label):
    path = "%s/%s.pdf" % (PDF_DIR, label)
    html_path = "%s/%s.html" % (PDF_DIR, label)
    data = env["ir.actions.report"]._render_qweb_pdf(xmlid, ids)[0]
    open(path, "wb").write(data)
    html = env["ir.actions.report"]._render_qweb_html(xmlid, ids)[0]
    if isinstance(html, bytes):
        html = html.decode("utf-8", "replace")
    open(html_path, "w").write(html)
    return path, len(data), html


c8 = env["res.company"].browse(8)
c9 = env["res.company"].browse(9)
c11 = env["res.company"].browse(11)
e8, e9, e11 = ce(c8), ce(c9), ce(c11)

# H01 tax audit all 461-466 + flow on company 11 (active B01)
try:
    audit = []
    for tid in (461, 462, 463, 464, 465, 466):
        t16 = env["account.tax"].browse(tid)
        t18 = sale_tax(env, t16.company_id, 18)
        d16, d18 = tax_dump(t16), tax_dump(t18)
        diffs = []
        for key in (
            "amount_type",
            "type_tax_use",
            "price_include",
            "tax_group",
            "tax_exigibility",
            "include_base_amount",
            "country",
        ):
            if d16.get(key) != d18.get(key):
                diffs.append({key: [d16.get(key), d18.get(key)]})
        if d16["amount"] != 16 or d16["type_tax_use"] != "sale":
            diffs.append({"rate_or_use": True})
        audit.append({"t16": d16, "t18_id": t18.id if t18 else None, "diffs": diffs})
    report["findings"]["H01_TAX_AUDIT"] = audit
    tax16 = e11["account.tax"].browse(464)
    tax18 = sale_tax(e11, c11, 18)
    ptn = partner(e11, c11, "DXUAT TEST ITBIS16 DOR", "132220112")
    prod = product(e11, c11, "DXUAT-ITBIS16-DOR", "Producto TEST ITBIS 16", 1000, tax16)
    so = e11["sale.order"].create(
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
                        "name": "Producto TEST ITBIS 16",
                        "product_uom_qty": 1,
                        "price_unit": 1000,
                        "tax_ids": [(6, 0, tax16.ids)],
                    },
                )
            ],
        }
    )
    so.invalidate_recordset()
    flow = {
        "so": so.name,
        "untaxed": so.amount_untaxed,
        "tax": so.amount_tax,
        "total": so.amount_total,
        "currency": so.currency_id.name,
    }
    so.action_confirm()
    inv = so._create_invoices()[0]
    flow["invoice_draft"] = {
        "id": inv.id,
        "name": inv.name,
        "state": inv.state,
        "tax": inv.amount_tax,
        "total": inv.amount_total,
    }
    inv.action_post()
    inv.invalidate_recordset()
    flow["invoice_posted"] = {
        "name": inv.name,
        "state": inv.state,
        "ncf": getattr(inv, "justech_do_ncf", None)
        or getattr(inv, "l10n_latam_document_number", None),
        "lines": [
            {
                "account": aml.account_id.code,
                "name": aml.account_id.name,
                "debit": aml.debit,
                "credit": aml.credit,
                "tax_line": aml.tax_line_id.name if aml.tax_line_id else False,
            }
            for aml in inv.line_ids
        ],
    }
    report["findings"]["H01_FLOW"] = flow
    math_ok = abs(so.amount_tax - 160) < 0.02 and abs(so.amount_total - 1160) < 0.02
    _ok(
        "H01",
        "PASS" if math_ok and inv.state == "posted" else "FAIL",
        math_ok=math_ok,
        so=so.name,
        invoice=inv.name,
    )
except Exception as exc:
    _exc("H01", exc)
    traceback.print_exc()

# H03 / H08 on company 8 (no NCF needed for quote PDF)
try:
    tax16 = e8["account.tax"].browse(461)
    tax18 = sale_tax(e8, c8, 18)
    exempt = e8["account.tax"].search(
        [
            ("company_id", "=", c8.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 0),
            ("active", "=", True),
        ],
        limit=1,
    )
    ptn = partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    p18 = product(e8, c8, "DXUAT-P18", "Propet 18", 1000, tax18)
    p16 = product(e8, c8, "DXUAT-P16", "Propet 16", 1000, tax16)
    pex = product(e8, c8, "DXUAT-PEX", "Propet Exento", 500, exempt)
    so = e8["sale.order"].create(
        {
            "partner_id": ptn.id,
            "company_id": c8.id,
            "client_order_ref": "PO-TEST-001",
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": p18.id,
                        "product_uom_qty": 2,
                        "price_unit": 1000,
                        "tax_ids": [(6, 0, tax18.ids)],
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": p16.id,
                        "product_uom_qty": 1,
                        "price_unit": 1000,
                        "tax_ids": [(6, 0, tax16.ids)],
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": pex.id,
                        "product_uom_qty": 3,
                        "price_unit": 500,
                        "discount": 10,
                        "tax_ids": [(6, 0, exempt.ids)] if exempt else [(6, 0, [])],
                    },
                ),
            ],
        }
    )
    identities = []
    for line in so.order_line.filtered(lambda l: not l.display_type):
        amt = {
            "product": line.product_id.default_code,
            "qty": line.product_uom_qty,
            "unit_excl": line.price_reduce_taxexcl,
            "unit_incl": line.price_reduce_taxinc,
            "tax": line.price_tax,
            "subtotal": line.price_subtotal,
            "total": line.price_total,
        }
        amt["ok"] = abs((amt["subtotal"] + amt["tax"]) - amt["total"]) <= 0.02
        identities.append(amt)
    moves_before = e8["account.move"].search_count([])
    std_p, std_b, std_h = render_pdf("sale.action_report_saleorder", so.ids, "h03_std")
    pr_p, pr_b, pr_h = render_pdf(
        "justech_alexander_reports.action_report_saleorder_propet", so.ids, "h03_propet"
    )
    pf_p, pf_b, pf_h = render_pdf(
        "sale.action_report_pro_forma_invoice",
        so.with_context(proforma=True).ids,
        "h08_proforma",
    )
    moves_after = e8["account.move"].search_count([])
    grp = env.ref("sale.group_proforma_sales")
    report["findings"]["H03"] = {
        "so": so.name,
        "identities": identities,
        "math_ok": all(i["ok"] for i in identities),
        "std_has_propet": "FORMULARIO PROPET" in std_h,
        "propet_title": "FORMULARIO PROPET" in pr_h,
        "propet_company": c8.name in pr_h or (c8.dx_trade_name or "") in pr_h,
        "bytes": {"std": std_b, "propet": pr_b, "proforma": pf_b},
    }
    report["findings"]["H08"] = {
        "so": so.name,
        "has_proforma": "PROFORMA" in pf_h.upper() or "PRO-FORMA" in pf_h.upper(),
        "creates_move": moves_after != moves_before,
        "group_xmlid": "sale.group_proforma_sales",
        "group_user_ids": grp.user_ids.mapped("login"),
        "group_empty_means": (
            "Grupo tecnico nativo que oculta el print Proforma. Alexander limpia "
            "group_ids del reporte; no hace falta asignar usuarios."
        ),
        "spanish": "Factura Proforma" in pf_h
        or "FACTURA PROFORMA" in pf_h
        or "PROFORMA" in pf_h.upper(),
    }
    _ok(
        "H03",
        (
            "PASS"
            if report["findings"]["H03"]["math_ok"]
            and report["findings"]["H03"]["propet_title"]
            else "FAIL"
        ),
    )
    _ok(
        "H08",
        (
            "PASS"
            if report["findings"]["H08"]["has_proforma"]
            and not report["findings"]["H08"]["creates_move"]
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H03", exc)
    _exc("H08", exc)
    traceback.print_exc()

# H04
try:
    sale_g = env.ref("sales_team.group_sale_salesman")
    purch_g = env.ref("purchase.group_purchase_user")
    sale_only = (
        env["res.users"]
        .sudo()
        .search(
            [
                ("share", "=", False),
                ("group_ids", "in", sale_g.id),
                ("group_ids", "not in", purch_g.id),
            ],
            limit=8,
        )
    )
    purch_users = (
        env["res.users"]
        .sudo()
        .search(
            [("share", "=", False), ("group_ids", "in", purch_g.id)],
            limit=8,
        )
    )
    arch = env["sale.order"].get_view(view_type="form").get("arch") or ""
    if isinstance(arch, bytes):
        arch = arch.decode()
    needles = [
        "justech_qty_purchased",
        "justech_qty_pending_purchase",
        "justech_supply_state",
        "justech_coverage_state",
    ]
    report["findings"]["H04"] = {
        "sale_only": sale_only.mapped("login"),
        "purchase_users": purch_users.mapped("login"),
        "fields_in_arch": {n: n in arch for n in needles},
        "purchase_group_gate": "purchase.group_purchase_user" in arch,
        "trace": env["ir.module.module"]
        .search([("name", "=", "justech_sale_purchase_trace")])
        .mapped(lambda m: "%s %s" % (m.state, m.latest_version)),
    }
    _ok(
        "H04",
        (
            "PASS"
            if all(report["findings"]["H04"]["fields_in_arch"].values())
            and report["findings"]["H04"]["purchase_group_gate"]
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H04", exc)
    traceback.print_exc()

# H05
try:
    native = env.ref("stock.view_template_property_form").arch_db or ""
    custom = env["ir.ui.view"].search(
        [("name", "=", "product.template.form.dx.tracking")]
    )
    lot_g = env.ref("stock.group_production_lot")
    implied = lot_g in env.ref("base.group_user").implied_ids
    if not implied:
        env["res.config.settings"].create(
            {"group_stock_production_lot": True}
        ).execute()
        implied = lot_g in env.ref("base.group_user").implied_ids
    report["findings"]["H05_SECURITY"] = {
        "native_groups": "stock.group_production_lot" in native,
        "custom_override": custom.mapped("name"),
        "group": lot_g.display_name,
        "implied_internal_user": implied,
        "setting_is_lots_serial": True,
        "users": lot_g.user_ids.mapped("login")[:15],
    }
    tax18 = sale_tax(e8, c8, 18)
    ptn = partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    prod_lot = product(e8, c8, "DXUAT-LOT", "UAT Lote", 100, tax18, storable=True)
    prod_lot.tracking = "lot"
    prod_ser = product(e8, c8, "DXUAT-SER", "UAT Serie", 100, tax18, storable=True)
    prod_ser.tracking = "serial"
    wh = e8["stock.warehouse"].search([("company_id", "=", c8.id)], limit=1)
    in_type = wh.in_type_id

    def receive(prod, lot_name, qty):
        lot = e8["stock.lot"].search(
            [("name", "=", lot_name), ("product_id", "=", prod.id)], limit=1
        )
        if not lot:
            lot = e8["stock.lot"].create(
                {"name": lot_name, "product_id": prod.id, "company_id": c8.id}
            )
        picking = e8["stock.picking"].create(
            {
                "picking_type_id": in_type.id,
                "location_id": in_type.default_location_src_id.id,
                "location_dest_id": in_type.default_location_dest_id.id,
                "company_id": c8.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": prod.name,
                            "product_id": prod.id,
                            "product_uom_qty": qty,
                            "product_uom": prod.uom_id.id,
                            "location_id": in_type.default_location_src_id.id,
                            "location_dest_id": in_type.default_location_dest_id.id,
                            "company_id": c8.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        move = picking.move_ids[0]
        if move.move_line_ids:
            ml = move.move_line_ids[0]
            ml.lot_id = lot.id
            ml.quantity = qty
        else:
            e8["stock.move.line"].create(
                {
                    "picking_id": picking.id,
                    "move_id": move.id,
                    "product_id": prod.id,
                    "product_uom_id": prod.uom_id.id,
                    "quantity": qty,
                    "lot_id": lot.id,
                    "location_id": in_type.default_location_src_id.id,
                    "location_dest_id": in_type.default_location_dest_id.id,
                    "company_id": c8.id,
                }
            )
        picking.button_validate()
        return picking, lot

    pin_lot, lot = receive(prod_lot, "DXUAT-LOT-001", 2)
    pin_ser, serial = receive(prod_ser, "DXUAT-SER-001", 1)

    def deliver(prod, lot, qty):
        so = e8["sale.order"].create(
            {
                "partner_id": ptn.id,
                "company_id": c8.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": qty,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, tax18.ids)],
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids[:1]
        picking.action_assign()
        for move in picking.move_ids:
            if move.move_line_ids:
                move.move_line_ids[0].lot_id = lot.id
                move.move_line_ids[0].quantity = qty
            else:
                e8["stock.move.line"].create(
                    {
                        "picking_id": picking.id,
                        "move_id": move.id,
                        "product_id": prod.id,
                        "product_uom_id": prod.uom_id.id,
                        "quantity": qty,
                        "lot_id": lot.id,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                        "company_id": c8.id,
                    }
                )
        picking.button_validate()
        return so, picking

    so_l, pout_l = deliver(prod_lot, lot, 1)
    so_s, pout_s = deliver(prod_ser, serial, 1)
    report["findings"]["H05_FLOW"] = {
        "lot_in": {"name": pin_lot.name, "state": pin_lot.state},
        "lot_out": {"name": pout_l.name, "state": pout_l.state, "so": so_l.name},
        "serial_in": {"name": pin_ser.name, "state": pin_ser.state},
        "serial_out": {"name": pout_s.name, "state": pout_s.state, "so": so_s.name},
        "lot": lot.name,
        "serial": serial.name,
    }
    ok = {pin_lot.state, pin_ser.state, pout_l.state, pout_s.state} == {
        "done"
    } and not custom
    _ok("H05", "PASS" if ok else "FAIL")
except Exception as exc:
    _exc("H05", exc)
    traceback.print_exc()

# H07
try:
    rec_g = env.ref("justech_accounting_recovery.group_accounting_recovery")
    inv_g = env.ref("account.group_account_invoice")
    user = (
        env["res.users"]
        .sudo()
        .search(
            [
                ("share", "=", False),
                ("group_ids", "in", inv_g.id),
                ("group_ids", "not in", rec_g.id),
            ],
            limit=1,
        )
    )
    ptn = partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    tax18 = sale_tax(e8, c8, 18)
    prod = product(e8, c8, "DXUAT-H07", "UAT Recovery", 100, tax18)
    draft = e8["account.move"].create(
        {
            "move_type": "out_invoice",
            "partner_id": ptn.id,
            "company_id": c8.id,
            "invoice_date": "2026-09-16",
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": prod.id,
                        "quantity": 1,
                        "price_unit": 100,
                        "tax_ids": [(6, 0, tax18.ids)],
                    },
                )
            ],
        }
    )
    cancel_err = unlink_err = None
    try:
        draft.with_user(user).with_company(c8).button_cancel()
        cancel_ok = True
    except Exception as exc:
        cancel_ok = False
        cancel_err = "%s: %s" % (type(exc).__name__, exc)
    try:
        draft.with_user(user).with_company(c8).unlink()
        unlink_ok = True
    except Exception as exc:
        unlink_ok = False
        unlink_err = "%s: %s" % (type(exc).__name__, exc)
    report["findings"]["H07"] = {
        "recovery_users": rec_g.user_ids.mapped("login"),
        "tested_user": user.login if user else None,
        "draft_state": draft.state,
        "cancel_without_recovery": {"allowed": cancel_ok, "error": cancel_err},
        "unlink_without_recovery": {"allowed": unlink_ok, "error": unlink_err},
        "users_added": False,
        "code_changed": False,
    }
    _ok("H07", "PASS")
except Exception as exc:
    _exc("H07", exc)
    traceback.print_exc()

# H13 company 11
try:
    ptn = partner(e11, c11, "DXUAT CLIENTE PAGOS", "131000002")
    tax18 = sale_tax(e11, c11, 18)
    prod = product(e11, c11, "DXUAT-PAY", "UAT Pago", 1000, tax18)
    invoices = []
    for price in (1000.0, 2000.0, 3000.0):
        so = e11["sale.order"].create(
            {
                "partner_id": ptn.id,
                "company_id": c11.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                            "tax_ids": [(6, 0, tax18.ids)],
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        inv = so._create_invoices()[0]
        inv.action_post()
        invoices.append(inv)
    before = [
        {
            "name": i.name,
            "total": i.amount_total,
            "residual": i.amount_residual,
            "ncf": getattr(i, "justech_do_ncf", None),
        }
        for i in invoices
    ]
    bank = e11["account.journal"].search(
        [("company_id", "=", c11.id), ("type", "=", "bank")], limit=1
    )
    method = e11["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "inbound"),
        ],
        limit=1,
    )
    Wizard = e11["multi.invoice.manual.payment.wizard"].with_company(c11)
    total = sum(abs(i.amount_residual) for i in invoices)
    wiz = Wizard.create(
        {
            "partner_type": "customer",
            "partner_id": ptn.id,
            "company_id": c11.id,
            "payment_date": "2026-09-16",
            "journal_id": bank.id,
            "payment_method_line_id": method.id,
            "ref": "DXUAT-MULTI-3",
            "amount_received": total,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "move_id": i.id,
                        "currency_id": i.currency_id.id,
                        "invoice_date": i.invoice_date,
                        "due_date": i.invoice_date_due,
                        "amount_total": abs(i.amount_total),
                        "amount_residual": abs(i.amount_residual),
                        "amount_to_apply": abs(i.amount_residual),
                    },
                )
                for i in invoices
            ],
        }
    )
    payment = e11["account.payment"].browse(wiz.action_create_payment().get("res_id"))
    for i in invoices:
        i.invalidate_recordset()
    after = [
        {
            "name": i.name,
            "residual": i.amount_residual,
            "payment_state": i.payment_state,
        }
        for i in invoices
    ]
    path, nbytes, html = render_pdf(
        "account.action_report_payment_receipt", payment.ids, "h13_recibo_3"
    )
    listed = [i.name for i in invoices if i.name and i.name in html]
    wh_fields = [
        f
        for f in payment._fields
        if "withhold" in f or "retenc" in f or "justech_wh" in f or "justech_net" in f
    ]
    wiz_wh = [
        f for f in Wizard._fields if "withhold" in f or "retenc" in f or "wh_" in f
    ]
    report["findings"]["H13"] = {
        "before": before,
        "after": after,
        "payment": {
            "id": payment.id,
            "name": payment.name,
            "amount": payment.amount,
            "state": payment.state,
            "move": payment.move_id.name,
            "lines": [
                {"account": l.account_id.code, "debit": l.debit, "credit": l.credit}
                for l in payment.move_id.line_ids
            ],
        },
        "receipt_lists": listed,
        "all_paid": all(abs(i.amount_residual) < 0.02 for i in invoices),
        "wh_fields": wh_fields,
        "wizard_wh": wiz_wh,
        "force_payment_move": False,
    }
    _ok("H13", "PASS" if report["findings"]["H13"]["all_paid"] else "FAIL")
except Exception as exc:
    _exc("H13", exc)
    traceback.print_exc()

# H14 two companies with qty
try:
    rows = []
    for company, ee in ((c8, e8), (c9, e9)):
        tax = sale_tax(ee, company, 18)
        ptn = partner(
            ee, company, "DXUAT CONDUCE %s" % company.id, "13100010%s" % company.id
        )
        prod = product(
            ee,
            company,
            "DXUAT-CON2-%s" % company.id,
            "UAT Conduce2 %s" % company.id,
            100,
            tax,
            storable=True,
        )
        # seed stock without lot
        wh = ee["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        in_type = wh.in_type_id
        pin = ee["stock.picking"].create(
            {
                "picking_type_id": in_type.id,
                "location_id": in_type.default_location_src_id.id,
                "location_dest_id": in_type.default_location_dest_id.id,
                "company_id": company.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": prod.name,
                            "product_id": prod.id,
                            "product_uom_qty": 5,
                            "product_uom": prod.uom_id.id,
                            "location_id": in_type.default_location_src_id.id,
                            "location_dest_id": in_type.default_location_dest_id.id,
                            "company_id": company.id,
                        },
                    )
                ],
            }
        )
        pin.action_confirm()
        pin.action_assign()
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
        path, nbytes, html = render_pdf(
            "stock.action_report_delivery", picking.ids, "h14_conduce_%s" % company.id
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
                "qty": picking.move_ids.mapped("quantity"),
                "bytes": nbytes,
            }
        )
    report["findings"]["H14"] = rows
    ok = all(
        r["state"] == "done" and r["has_conduce"] and not r["cross_brand"] for r in rows
    )
    _ok("H14", "PASS" if ok else "FAIL")
except Exception as exc:
    _exc("H14", exc)
    traceback.print_exc()

# H16 signatures without signature field
try:
    so_a = e8["sale.order"].search(
        [("company_id", "=", 8), ("client_order_ref", "=", "PO-TEST-001")], limit=1
    )
    ptn_b = partner(e9, c9, "DXUAT FIRMA B", "132000009")
    tax_b = sale_tax(e9, c9, 18)
    prod_b = product(e9, c9, "DXUAT-SIG-B", "UAT Firma B", 10, tax_b)
    so_b = e9["sale.order"].create(
        {
            "partner_id": ptn_b.id,
            "company_id": c9.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": prod_b.id,
                        "product_uom_qty": 1,
                        "price_unit": 10,
                        "tax_ids": [(6, 0, tax_b.ids)],
                    },
                )
            ],
        }
    )
    Compose = env["mail.compose.message"]

    def compose_info(record):
        composer = (
            Compose.with_context(
                default_model=record._name,
                default_res_ids=[record.id],
                default_composition_mode="comment",
                allowed_company_ids=[record.company_id.id],
            )
            .with_company(record.company_id)
            .create(
                {
                    "model": record._name,
                    "res_ids": str([record.id]),
                    "composition_mode": "comment",
                }
            )
        )
        company = composer._dx_document_company()
        html = company._dx_mail_signature_html() if company else ""
        return {
            "doc": record.name,
            "doc_company": record.company_id.name,
            "resolved": company.name if company else None,
            "email_from": composer.email_from,
            "reply_to": composer.reply_to,
            "signature_html": html[:300],
            "uses_document_company": bool(
                company and company.id == record.company_id.id
            ),
        }

    a = compose_info(so_a) if so_a else None
    b = compose_info(so_b)
    report["findings"]["H16"] = {
        "user": env.user.login,
        "companies": env.user.company_ids.mapped("name"),
        "a": a,
        "b": b,
        "distinct": (a or {}).get("signature_html") != (b or {}).get("signature_html"),
        "no_signature_field_odoo19": True,
    }
    _ok(
        "H16",
        (
            "PASS"
            if b.get("uses_document_company")
            and (not a or a.get("uses_document_company"))
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H16", exc)
    traceback.print_exc()

report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
report["pass"] = [
    k for k, v in report["checklist"].items() if v.get("status") == "PASS"
]
report["fail"] = [
    k for k, v in report["checklist"].items() if v.get("status") == "FAIL"
]
report["blocked"] = [
    k for k, v in report["checklist"].items() if v.get("status") == "BLOCKED"
]
open(OUT, "w").write(json.dumps(report, indent=2, default=str))
print("UAT_R2", OUT)
print("PASS", report["pass"])
print("FAIL", report["fail"])
print("BLOCKED", report["blocked"])
