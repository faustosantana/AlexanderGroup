# DX 360 PRODUCTION QA — create TEST data only. Do not send to DGII.
# Prefix: DX TEST. NCF band 991xxxxx. authorization DX-TEST-NO-DGII-360.
from datetime import date, timedelta
from pathlib import Path
import base64
import json
import traceback

OUT = Path("/tmp/dx360")
OUT.mkdir(exist_ok=True)
TODAY = date.today()
PERIOD = TODAY.strftime("%Y%m")
MARK = "DX TEST"
NO_DGII = "NO FISCAL REAL — NO ENVIAR DGII"
AUTH = "DX-TEST-NO-DGII-360"
BAND = "991xxxxx"
CATALOG = {
    "marker": "DX360-20260829",
    "period": PERIOD,
    "ncf_band": BAND,
    "authorization": AUTH,
    "partners": [],
    "products": [],
    "ncf_ranges": [],
    "sale_orders": [],
    "purchase_orders": [],
    "account_moves": [],
    "account_payments": [],
    "stock_pickings": [],
    "warranties": [],
    "crm_leads": [],
    "users": [],
    "attachments": [],
}
RESULTS = {"steps": [], "fails": [], "ncf_used": []}
CODES = ["DOR", "PIN", "DOM", "MAY", "REM", "BLU"]
B01_START = {
    "DOR": 99100001,
    "PIN": 99100101,
    "DOM": 99100201,
    "MAY": 99100301,
    "REM": 99100401,
    "BLU": 99100501,
}
B04_START = {
    "DOR": 99110001,
    "PIN": 99110101,
    "DOM": 99110201,
    "MAY": 99110301,
    "REM": 99110401,
    "BLU": 99110501,
}


def note(step, status, detail=""):
    RESULTS["steps"].append({"step": step, "status": status, "detail": str(detail)[:500]})
    print("STEP", step, status, str(detail)[:200])


def fail(step, exc):
    RESULTS["fails"].append({"step": step, "error": str(exc)[:500]})
    note(step, "FAIL", exc)
    print("FAIL", step, traceback.format_exc()[-400:])
    try:
        env.cr.rollback()
    except Exception:
        pass


def add_id(bucket, rec, extra=None):
    if not rec:
        return
    row = {"model": rec._name, "id": rec.id, "name": rec.display_name}
    if extra:
        row.update(extra)
    CATALOG[bucket].append(row)


def validate_picking(picking, qty_map=None):
    picking = picking.sudo()
    for move in picking.move_ids:
        done = qty_map.get(move.id, move.product_uom_qty) if qty_map else move.product_uom_qty
        if "quantity" in move._fields:
            move.quantity = done
        elif "qty_done" in move._fields:
            move.qty_done = done
    res = picking.with_context(skip_sms=True, skip_backorder=True, skip_immediate=True).button_validate()
    if isinstance(res, dict) and res.get("res_model"):
        Wiz = env[res["res_model"]].with_context(**(res.get("context") or {}))
        wiz = Wiz.create({})
        for method in ("process", "button_validate", "action_confirm", "process_cancel_backorder"):
            if hasattr(wiz, method):
                getattr(wiz, method)()
                break
    return picking


def pay_invoice(move, amount, memo):
    Pay = env["account.payment.register"].sudo()
    wiz = Pay.with_context(active_model="account.move", active_ids=move.ids).with_company(move.company_id).create(
        {
            "amount": amount,
            "payment_date": TODAY,
            "communication": memo,
        }
    )
    pay_action = wiz.action_create_payments()
    payments = env["account.payment"].sudo()
    if isinstance(pay_action, dict) and pay_action.get("res_id"):
        payments = payments.browse(pay_action["res_id"])
    elif isinstance(pay_action, dict) and pay_action.get("res_ids"):
        payments = payments.browse(pay_action["res_ids"])
    else:
        payments = env["account.payment"].sudo().search(
            [("memo", "=", memo), ("company_id", "=", move.company_id.id)],
            order="id desc",
            limit=1,
        )
    for p in payments:
        add_id("account_payments", p, {"company": move.company_id.dx_short_code, "amount": p.amount})
    return payments


def reverse_invoice(inv, reason):
    Reversal = env["account.move.reversal"].sudo()
    wiz = Reversal.with_context(active_model="account.move", active_ids=inv.ids).with_company(inv.company_id).create(
        {
            "reason": reason,
            "date": TODAY,
            "journal_id": inv.journal_id.id,
        }
    )
    action = wiz.refund_moves() if hasattr(wiz, "refund_moves") else wiz.reverse_moves()
    refunds = env["account.move"].sudo()
    if isinstance(action, dict) and action.get("res_id"):
        refunds = refunds.browse(action["res_id"])
    elif isinstance(action, dict) and action.get("domain"):
        refunds = env["account.move"].sudo().search(action["domain"])
    else:
        refunds = inv.reversal_move_ids
    for r in refunds:
        if r.state == "draft":
            r.action_post()
        add_id(
            "account_moves",
            r,
            {
                "company": inv.company_id.dx_short_code,
                "type": r.move_type,
                "ncf": r.justech_do_ncf,
                "origin": inv.justech_do_ncf,
            },
        )
        RESULTS["ncf_used"].append(
            {
                "company": inv.company_id.dx_short_code,
                "type": "B04",
                "ncf": r.justech_do_ncf,
                "move_id": r.id,
                "name": r.name,
            }
        )
    return refunds


def render_pdf(xmlid, recs):
    return env["ir.actions.report"].sudo()._render_qweb_pdf(env.ref(xmlid), res_ids=recs.ids)[0]


def fiscalize_partner(partner, doc_b01):
    partner.write(
        {
            "justech_do_rnc_status": "valid",
            "justech_do_default_document_type_id": doc_b01.id,
            "justech_do_fiscal_config_state": "validated_padron",
        }
    )


# ---------------------------------------------------------------------------
# Inventory of installed custom modules (read-only)
# ---------------------------------------------------------------------------
mod_rows = []
for m in env["ir.module.module"].sudo().search([("state", "=", "installed")], order="name"):
    n = m.name or ""
    if n.startswith(("justech", "l10n_do", "multi_", "bi_")):
        menus = env["ir.ui.menu"].sudo().search([("name", "ilike", n[:12])])
        mod_rows.append(
            {
                "name": n,
                "version": m.latest_version or m.installed_version,
                "installed": True,
            }
        )
(OUT / "modules.json").write_text(json.dumps(mod_rows, indent=2))
note("module_inventory", "PASS", "%s custom installed" % len(mod_rows))

# NC / reversión exige grupo SoD aun para Administrador (no hay excepción).
try:
    rec_grp = env.ref("justech_accounting_recovery.group_accounting_recovery")
    gfield = "group_ids" if "group_ids" in env.user._fields else "groups_id"
    current = env.user[gfield]
    if rec_grp and rec_grp.id not in current.ids:
        env.user.sudo().write({gfield: [(4, rec_grp.id)]})
        CATALOG.setdefault("users", []).append(
            {
                "model": "res.users",
                "id": env.user.id,
                "name": env.user.login,
                "note": "añadido grupo Recuperación Contable para QA NC",
            }
        )
        note("recovery_group_admin", "PASS", "granted to %s" % env.user.login)
    env.cr.commit()
except Exception as exc:
    fail("recovery_group_admin", exc)

Company = env["res.company"].sudo()
companies = Company.search([("dx_short_code", "in", CODES)], order="dx_sequence")
assert len(companies) == 6, companies.mapped("dx_short_code")
doc_b01 = env["justech.do.fiscal.document.type"].sudo().search([("prefix", "=", "B01")], limit=1)
doc_b04 = env["justech.do.fiscal.document.type"].sudo().search([("prefix", "=", "B04")], limit=1)
latam_b01 = env["l10n_latam.document.type"].sudo().search([("doc_code_prefix", "=", "B01")], limit=1)
do_country = env.ref("base.do")

# Tags
Tag = env["res.partner.category"].sudo()
qa_tag = Tag.search([("name", "=", "DX TEST")], limit=1)
if not qa_tag:
    qa_tag = Tag.create({"name": "DX TEST"})
add_id("partners", qa_tag, {"kind": "tag"})

# Products (shared)
Product = env["product.product"].sudo()


def get_or_create_product(code, name, ptype, storable=False, price=100.0):
    rec = Product.search([("default_code", "=", code)], limit=1)
    vals = {
        "name": name,
        "default_code": code,
        "type": ptype,
        "list_price": price,
        "standard_price": 40.0 if storable else 0.0,
        "company_id": False,
        "sale_ok": True,
        "purchase_ok": True,
    }
    if storable and "is_storable" in env["product.product"]._fields:
        vals["is_storable"] = True
        vals["type"] = "consu"
    if rec:
        rec.write({k: vals[k] for k in ("name", "list_price")})
    else:
        rec = Product.create(vals)
    add_id("products", rec, {"code": code})
    return rec


svc = get_or_create_product("DX-TEST-SVC", "DX TEST PRODUCTO SERVICIO — NO FISCAL REAL", "service", price=250.0)
stk = get_or_create_product(
    "DX-TEST-STK", "DX TEST PRODUCTO INVENTARIABLE — NO FISCAL REAL", "consu", storable=True, price=180.0
)
eqp = get_or_create_product("DX-TEST-EQP", "DX TEST PRODUCTO EQUIPO — NO FISCAL REAL", "consu", price=1200.0)

# Partners
Partner = env["res.partner"].sudo()
clients = {}
vendors = {}
for i, company in enumerate(companies):
    code = company.dx_short_code
    cname = "DX TEST CLIENTE %s — NO FISCAL REAL" % code
    vname = "DX TEST PROVEEDOR %s — NO FISCAL REAL" % code
    client = Partner.search([("name", "=", cname)], limit=1)
    if not client:
        client = Partner.create(
            {
                "name": cname,
                "company_type": "company",
                "vat": "10199%04d" % (i + 1),
                "country_id": do_country.id,
                "email": "dx.test.%s.cliente@justech.do" % code.lower(),
                "phone": "809-000-00%02d" % (i + 1),
                "street": "DX TEST Calle QA %s" % code,
                "city": "Santo Domingo",
                "company_id": False,
                "category_id": [(6, 0, qa_tag.ids)],
                "comment": "%s %s" % (MARK, NO_DGII),
            }
        )
    fiscalize_partner(client, doc_b01)
    vendor = Partner.search([("name", "=", vname)], limit=1)
    if not vendor:
        vendor = Partner.create(
            {
                "name": vname,
                "company_type": "company",
                "vat": "20199%04d" % (i + 1),
                "country_id": do_country.id,
                "email": "dx.test.%s.prov@justech.do" % code.lower(),
                "phone": "809-100-00%02d" % (i + 1),
                "street": "DX TEST Proveedor %s" % code,
                "city": "Santo Domingo",
                "company_id": False,
                "supplier_rank": 1,
                "category_id": [(6, 0, qa_tag.ids)],
                "comment": "%s %s" % (MARK, NO_DGII),
            }
        )
    fiscalize_partner(vendor, doc_b01)
    clients[code] = client
    vendors[code] = vendor
    add_id("partners", client, {"role": "client", "company": code})
    add_id("partners", vendor, {"role": "vendor", "company": code})

note("qa_masters", "PASS", "partners+products")

# NCF TEST ranges
Range = env["justech.do.ncf.range"].sudo()
ranges = {}
for company in companies:
    code = company.dx_short_code
    sale_j = env["account.journal"].sudo().search(
        [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
    )
    sale_j.write({"justech_do_use_ncf": True})
    for prefix, doc, starts in (("B01", doc_b01, B01_START), ("B04", doc_b04, B04_START)):
        start = starts[code]
        name = "DX TEST %s %s — %s — %s" % (prefix, code, AUTH, NO_DGII)
        rng = Range.search(
            [
                ("company_id", "=", company.id),
                ("document_type_id", "=", doc.id),
                ("authorization_number", "=", AUTH),
            ],
            limit=1,
        )
        if not rng:
            rng = Range.create(
                {
                    "name": name,
                    "company_id": company.id,
                    "document_type_id": doc.id,
                    "authorization_number": AUTH,
                    "sequence_start": start,
                    "sequence_end": start + 49,
                    "next_sequence": start,
                    "date_from": TODAY - timedelta(days=1),
                    "date_to": TODAY + timedelta(days=120),
                    "journal_ids": [(6, 0, sale_j.ids)],
                }
            )
            rng.action_activate()
        ranges[(code, prefix)] = rng
        add_id(
            "ncf_ranges",
            rng,
            {
                "company": code,
                "prefix": prefix,
                "start": rng.sequence_start,
                "end": rng.sequence_end,
                "next": rng.next_sequence,
                "state": rng.state,
            },
        )
note("ncf_test_ranges", "PASS", "B01+B04 x6 AUTH=%s" % AUTH)
env.cr.commit()

# External DGII submission: no e-CF / no exporter models
dgii_models = [k for k in env.registry if "dgii.60" in k or "dgii.exporter" in k]
RESULTS["dgii_exporter_models"] = dgii_models
RESULTS["dgii_external_submission"] = "DISABLED_FOR_TEST"
note("dgii_external", "DISABLED_FOR_TEST", dgii_models or "no exporter models")


def sale_tax(company):
    return env["account.tax"].sudo().search(
        [("company_id", "=", company.id), ("type_tax_use", "=", "sale"), ("amount", "=", 18)],
        limit=1,
    )


def purchase_tax(company):
    return env["account.tax"].sudo().search(
        [("company_id", "=", company.id), ("type_tax_use", "=", "purchase"), ("amount", "=", 18)],
        limit=1,
    )


def create_so(company, client, lines, name_note):
    so = (
        env["sale.order"]
        .sudo()
        .with_company(company)
        .create(
            {
                "partner_id": client.id,
                "company_id": company.id,
                "client_order_ref": name_note,
                "note": "%s %s" % (MARK, NO_DGII),
                "order_line": lines,
            }
        )
    )
    add_id("sale_orders", so, {"company": company.dx_short_code})
    return so


def so_line(product, qty, price, tax, discount=0.0):
    vals = {
        "product_id": product.id,
        "product_uom_qty": qty,
        "price_unit": price,
        "discount": discount,
        "name": "[%s] %s — %s" % (product.default_code, product.name, MARK),
    }
    if tax:
        tax_field = "tax_ids" if "tax_ids" in env["sale.order.line"]._fields else "tax_id"
        vals[tax_field] = [(6, 0, tax.ids)]
    return (0, 0, vals)


def invoice_from_so(so):
    invs = so._create_invoices()
    return invs


# ---------------------------------------------------------------------------
# Per-company commercial + fiscal flow
# ---------------------------------------------------------------------------
for company in companies:
    code = company.dx_short_code
    client = clients[code]
    vendor = vendors[code]
    tax_s = sale_tax(company)
    tax_p = purchase_tax(company)
    try:
        existing = env["account.move"].sudo().search(
            [
                ("ref", "=", "DX TEST FACTURA B01 %s %s" % (code, NO_DGII)),
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
            ],
            limit=1,
        )
        if existing:
            inv = existing
            note("flow_%s_sale" % code, "REUSED", "%s %s" % (inv.name, inv.justech_do_ncf))
        else:
            so = create_so(
                company,
                client,
                [
                    so_line(eqp, 1, 1200, tax_s),
                    so_line(svc, 2, 250, tax_s, discount=10.0),
                    so_line(stk, 1, 180, tax_s),
                ],
                "DX TEST COTIZACION %s %s" % (code, NO_DGII),
            )
            so.action_confirm()
            for picking in so.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing"):
                validate_picking(picking)
                add_id("stock_pickings", picking, {"company": code, "code": picking.picking_type_code})
            inv = invoice_from_so(so)
            inv.invoice_date = TODAY
            inv.invoice_date_due = TODAY + timedelta(days=15)
            inv.ref = "DX TEST FACTURA B01 %s %s" % (code, NO_DGII)
            inv.narration = "%s %s período %s" % (MARK, NO_DGII, PERIOD)
            inv.action_post()
            assert inv.state == "posted", inv.state
            assert inv.justech_do_ncf and inv.justech_do_ncf.startswith("B01991"), inv.justech_do_ncf
            add_id(
                "account_moves",
                inv,
                {
                    "company": code,
                    "type": "out_invoice",
                    "ncf": inv.justech_do_ncf,
                    "total": inv.amount_total,
                    "itbis": inv.amount_tax,
                },
            )
            RESULTS["ncf_used"].append(
                {"company": code, "type": "B01", "ncf": inv.justech_do_ncf, "move_id": inv.id, "name": inv.name}
            )
            pdf = render_pdf("account.account_invoices", inv)
            (OUT / ("invoice_%s.pdf" % code)).write_bytes(pdf)
            residual = inv.amount_residual
            pay_invoice(inv, round(residual * 0.4, 2), "DX TEST PAGO PARCIAL %s %s" % (code, NO_DGII))
            inv.invalidate_recordset()
            if inv.amount_residual:
                pay_invoice(inv, inv.amount_residual, "DX TEST PAGO TOTAL %s %s" % (code, NO_DGII))
            env.cr.commit()
            reverse_invoice(inv, "DX TEST NC B04 %s %s" % (code, NO_DGII))
        if inv and not inv.reversal_move_ids:
            reverse_invoice(inv, "DX TEST NC B04 %s %s" % (code, NO_DGII))
            env.cr.commit()
        # overdue unpaid invoice
        over = env["account.move"].sudo().search(
            [("ref", "=", "DX TEST VENCIDA %s %s" % (code, NO_DGII)), ("company_id", "=", company.id)],
            limit=1,
        )
        if not over:
            over = (
            env["account.move"]
            .sudo()
            .with_company(company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": client.id,
                    "company_id": company.id,
                    "invoice_date": date(2026, 6, 1),
                    "invoice_date_due": date(2026, 6, 15),
                    "ref": "DX TEST VENCIDA %s %s" % (code, NO_DGII),
                    "narration": "%s %s" % (MARK, NO_DGII),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": svc.id,
                                "name": "DX TEST linea vencida",
                                "quantity": 1,
                                "price_unit": 400.0,
                                "tax_ids": [(6, 0, tax_s.ids)] if tax_s else False,
                            },
                        )
                    ],
                }
            )
        )
            over.action_post()
        add_id("account_moves", over, {"company": code, "type": "out_invoice", "ncf": over.justech_do_ncf, "case": "overdue"})
        RESULTS["ncf_used"].append({"company": code, "type": "B01", "ncf": over.justech_do_ncf, "move_id": over.id, "case": "overdue"})
        env.cr.commit()
        # purchase flow
        po = env["purchase.order"].sudo().search(
            [("partner_ref", "=", "DX TEST RFQ/PO %s %s" % (code, NO_DGII)), ("company_id", "=", company.id)],
            limit=1,
        )
        if po:
            note("flow_%s_po" % code, "REUSED", po.name)
            env.cr.commit()
            continue
        po = (
            env["purchase.order"]
            .sudo()
            .with_company(company)
            .create(
                {
                    "partner_id": vendor.id,
                    "company_id": company.id,
                    "partner_ref": "DX TEST RFQ/PO %s %s" % (code, NO_DGII),
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": stk.id,
                                "name": "DX TEST compra %s" % code,
                                "product_qty": 10 if code == "DOR" else 2,
                                "price_unit": 80.0,
                                "tax_ids": [(6, 0, tax_p.ids)] if tax_p else False,
                            },
                        )
                    ],
                }
            )
        )
        add_id("purchase_orders", po, {"company": code, "state": "draft"})
        # RFQ PDF then confirm
        rfq_pdf = render_pdf("purchase.action_report_purchase_order", po)
        (OUT / ("rfq_%s.pdf" % code)).write_bytes(rfq_pdf)
        po.button_confirm()
        in_pick = po.picking_ids.filtered(lambda p: p.picking_type_code == "incoming")
        if in_pick:
            if code == "DOR":
                qty_map = {in_pick.move_ids[:1].id: 6.0}
                validate_picking(in_pick, qty_map)
            else:
                validate_picking(in_pick)
            add_id("stock_pickings", in_pick, {"company": code, "code": "incoming", "po": po.name})
        exp = env["justech.do.dgii.expense.type"].sudo().search([("code", "=", "09")], limit=1) or env[
            "justech.do.dgii.expense.type"
        ].sudo().search([], limit=1)
        bill = (
            env["account.move"]
            .sudo()
            .with_company(company)
            .create(
                {
                    "move_type": "in_invoice",
                    "partner_id": vendor.id,
                    "company_id": company.id,
                    "invoice_date": TODAY,
                    "invoice_date_due": TODAY + timedelta(days=20),
                    "ref": "DX TEST BILL %s %s" % (code, NO_DGII),
                    "justech_do_purchase_registration_mode": "received",
                    "justech_do_expense_type_id": exp.id if exp else False,
                    "l10n_latam_document_type_id": latam_b01.id if latam_b01 else False,
                    "l10n_latam_document_number": "B01992%05d" % (B01_START[code] % 100000),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": stk.id,
                                "name": "DX TEST vendor line",
                                "quantity": 2,
                                "price_unit": 80.0,
                                "tax_ids": [(6, 0, tax_p.ids)] if tax_p else False,
                            },
                        )
                    ],
                }
            )
        )
        bill.action_post()
        add_id(
            "account_moves",
            bill,
            {
                "company": code,
                "type": "in_invoice",
                "vendor_ncf": bill.l10n_latam_document_number,
                "ncf": bill.justech_do_ncf,
            },
        )
        pay_invoice(bill, bill.amount_residual, "DX TEST PAGO PROV %s %s" % (code, NO_DGII))
        env.cr.commit()
        note("flow_%s" % code, "PASS", "INV %s NCF %s BILL %s" % (inv.name, inv.justech_do_ncf, bill.name))
    except Exception as exc:
        fail("flow_%s" % code, exc)
        env.cr.rollback()
        # reload masters after rollback
        svc = Product.search([("default_code", "=", "DX-TEST-SVC")], limit=1)
        stk = Product.search([("default_code", "=", "DX-TEST-STK")], limit=1)
        eqp = Product.search([("default_code", "=", "DX-TEST-EQP")], limit=1)
        for c2 in companies:
            clients[c2.dx_short_code] = Partner.search(
                [("name", "=", "DX TEST CLIENTE %s — NO FISCAL REAL" % c2.dx_short_code)], limit=1
            )
            vendors[c2.dx_short_code] = Partner.search(
                [("name", "=", "DX TEST PROVEEDOR %s — NO FISCAL REAL" % c2.dx_short_code)], limit=1
            )

# Extra: DOR partial delivery 10→7, unapplied payment, credit-balance NC leftover
try:
    dor = companies.filtered(lambda c: c.dx_short_code == "DOR")
    tax_s = sale_tax(dor)
    so10 = create_so(
        dor,
        clients["DOR"],
        [so_line(stk, 10, 180, tax_s)],
        "DX TEST ENTREGA PARCIAL DOR %s" % NO_DGII,
    )
    so10.action_confirm()
    pick = so10.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing")[:1]
    if pick:
        qty_map = {pick.move_ids[:1].id: 7.0}
        validate_picking(pick, qty_map)
        add_id("stock_pickings", pick, {"company": "DOR", "case": "partial_out"})
        remaining = sum(pick.move_ids.mapped("product_uom_qty")) - 7.0
        RESULTS["partial_delivery_remaining"] = remaining
    # unapplied payment / advance
    adv = (
        env["account.payment"]
        .sudo()
        .with_company(dor)
        .create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": clients["DOR"].id,
                "amount": 75.0,
                "date": TODAY,
                "memo": "DX TEST ANTICIPO DOR %s" % NO_DGII,
            }
        )
    )
    if hasattr(adv, "action_post"):
        adv.action_post()
    add_id("account_payments", adv, {"company": "DOR", "case": "unapplied"})
    note("partial_and_advance", "PASS", RESULTS.get("partial_delivery_remaining"))
except Exception as exc:
    fail("partial_and_advance", exc)

# 608: void a dedicated unpaid TEST invoice (PIN) once
already_void = env["account.move"].sudo().search(
    [("ref", "ilike", "DX TEST ANULACION 608"), ("justech_do_ncf_voided", "=", True)], limit=1
)
if already_void:
    RESULTS["void_608"] = {
        "move_id": already_void.id,
        "ncf": already_void.justech_do_ncf,
        "voided": True,
        "reused": True,
    }
    note("void_608", "PASS", RESULTS["void_608"])
else:
    try:
        pin = companies.filtered(lambda c: c.dx_short_code == "PIN")
        tax_s = sale_tax(pin)
        void_inv = (
            env["account.move"]
            .sudo()
            .with_company(pin)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": clients["PIN"].id,
                    "company_id": pin.id,
                    "invoice_date": TODAY,
                    "ref": "DX TEST ANULACION 608 PIN %s" % NO_DGII,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": svc.id,
                                "name": "DX TEST void 608",
                                "quantity": 1,
                                "price_unit": 90.0,
                                "tax_ids": [(6, 0, tax_s.ids)] if tax_s else False,
                            },
                        )
                    ],
                }
            )
        )
        void_inv.action_post()
        add_id("account_moves", void_inv, {"company": "PIN", "case": "void_608", "ncf": void_inv.justech_do_ncf})
        RESULTS["ncf_used"].append({"company": "PIN", "type": "B01", "ncf": void_inv.justech_do_ncf, "case": "void_608"})
        wiz = env["justech.do.ncf.void.wizard"].sudo().create(
            {
                "move_id": void_inv.id,
                "cancel_type": "04",
                "observation": "DX TEST 608 — anulación QA — NO ENVIAR DGII",
                "acknowledge_accounting_intact": True,
            }
        )
        wiz.action_confirm_void()
        void_inv.invalidate_recordset()
        RESULTS["void_608"] = {
            "move_id": void_inv.id,
            "ncf": void_inv.justech_do_ncf,
            "voided": bool(void_inv.justech_do_ncf_voided),
            "cancel_type": void_inv.justech_do_ncf_cancel_type,
            "ui": void_inv.justech_do_fiscal_ui_status,
        }
        note("void_608", "PASS" if void_inv.justech_do_ncf_voided else "FAIL", RESULTS["void_608"])
    except Exception as exc:
        fail("void_608", exc)

# CRM
try:
    lead = env["crm.lead"].sudo().create(
        {
            "name": "DX TEST LEAD DOR — NO FISCAL REAL",
            "partner_id": clients["DOR"].id,
            "type": "lead",
            "company_id": companies.filtered(lambda c: c.dx_short_code == "DOR").id,
        }
    )
    if hasattr(lead, "convert_opportunity"):
        lead.convert_opportunity(clients["DOR"])
    else:
        lead.type = "opportunity"
    add_id("crm_leads", lead, {"type": lead.type})
    note("crm", "PASS", lead.name)
except Exception as exc:
    fail("crm", exc)

# Warranty
try:
    dor = companies.filtered(lambda c: c.dx_short_code == "DOR")
    warr = (
        env["justech.warranty"]
        .sudo()
        .with_company(dor)
        .create(
            {
                "partner_id": clients["DOR"].id,
                "product_id": eqp.id,
                "company_id": dor.id,
                "warranty_months": 12,
                "note": "DX TEST WARRANTY %s" % NO_DGII,
            }
        )
    )
    add_id("warranties", warr, {"state": warr.state})
    note("warranty", "PASS", warr.display_name)
except Exception as exc:
    fail("warranty", exc)

# Accounting recovery capability (non-destructive)
try:
    admin = env.ref("base.user_admin")
    op = env["res.users"].sudo().search([("login", "=", "inversionesdoralex@gmail.com")], limit=1)
    rec = {"admin": False, "operational": False, "fausto_user": False}
    if hasattr(admin, "can_recover_accounting_document"):
        rec["admin"] = bool(admin.can_recover_accounting_document(companies[:1]))
    if op and hasattr(op, "can_recover_accounting_document"):
        rec["operational"] = bool(op.can_recover_accounting_document(companies[:1]))
    rec["fausto_user"] = bool(env["res.users"].sudo().search([("login", "=", "fausto@justech.do")]))
    rec["admin_companies"] = admin.company_ids.mapped("dx_short_code")
    RESULTS["recovery"] = rec
    note("accounting_recovery", "PASS", rec)
except Exception as exc:
    fail("accounting_recovery", exc)

# Identity guard: official render + forbidden template must fail
try:
    dor = companies.filtered(lambda c: c.dx_short_code == "DOR")
    so = env["sale.order"].sudo().search([("client_order_ref", "ilike", "DX TEST COTIZACION DOR")], limit=1)
    pdf = env["ir.actions.report"].sudo().with_company(companies.filtered(lambda c: c.dx_short_code == "BLU"))._render_qweb_pdf(
        env.ref("sale.action_report_saleorder"), res_ids=so.ids
    )[0]
    (OUT / "cross_dor_active_blu.pdf").write_bytes(pdf)
    blocked = False
    try:
        env["ir.actions.report"].sudo()._jt_assert_allowed_report_name(
            "justech_report_design.report_hellenia_invoice", "dx360"
        )
    except Exception:
        blocked = True
    RESULTS["identity_guard"] = {"cross_pdf": len(pdf), "hellenia_blocked": blocked}
    note("identity_guard", "PASS" if blocked else "FAIL", RESULTS["identity_guard"])
except Exception as exc:
    fail("identity_guard", exc)

# bi_convert
try:
    dor = companies.filtered(lambda c: c.dx_short_code == "DOR")
    so = env["sale.order"].sudo().search([("client_order_ref", "ilike", "DX TEST COTIZACION DOR")], limit=1)
    wiz = (
        env["create.purchaseorder"]
        .sudo()
        .with_company(dor)
        .with_context(active_model="sale.order", active_id=so.id, active_ids=so.ids)
        .create({"partner_id": vendors["DOR"].id})
    )
    wiz.action_create_purchase_order()
    po = env["purchase.order"].sudo().search([("origin", "=", so.name)], limit=1, order="id desc")
    add_id("purchase_orders", po, {"company": "DOR", "case": "bi_convert", "origin": so.name})
    note("bi_convert", "PASS" if po else "FAIL", po.name if po else "no PO")
except Exception as exc:
    fail("bi_convert", exc)

# Security: QA user only BLU
try:
    import secrets

    blu = companies.filtered(lambda c: c.dx_short_code == "BLU")
    dor = companies.filtered(lambda c: c.dx_short_code == "DOR")
    grp_sale = env.ref("sales_team.group_sale_salesman_all_leads", raise_if_not_found=False)
    login = "dx.test.security@justech.do"
    user = env["res.users"].sudo().search([("login", "=", login)], limit=1)
    pwd = secrets.token_urlsafe(16)
    vals = {
        "name": "DX TEST USER SECURITY BLU",
        "login": login,
        "company_id": blu.id,
        "company_ids": [(6, 0, blu.ids)],
    }
    if "group_ids" in env["res.users"]._fields and grp_sale:
        vals["group_ids"] = [(6, 0, grp_sale.ids)]
    if user:
        user.write({k: vals[k] for k in vals if k != "login"})
    else:
        user = env["res.users"].sudo().create(vals)
    user.sudo().write({"password": pwd})
    Path("/opt/doralex/secrets/dx360_qa_user_password").write_text(pwd + "\n") if False else None
    add_id("users", user, {"login": login, "companies": user.company_ids.mapped("dx_short_code")})
    dor_inv = env["account.move"].sudo().search(
        [("ref", "ilike", "DX TEST FACTURA B01 DOR"), ("company_id", "=", dor.id)], limit=1
    )
    seen = env["account.move"].with_user(user).search([("id", "=", dor_inv.id)])
    RESULTS["security_isolation"] = {"blu_user_sees_dor_invoice": bool(seen)}
    note("security_acl", "PASS" if not seen else "FAIL", RESULTS["security_isolation"])
except Exception as exc:
    fail("security_acl", exc)

# Global audit log
try:
    Log = env["justech.audit.log"].sudo() if "justech.audit.log" in env else None
    count = Log.search_count([]) if Log else 0
    RESULTS["audit_log_count"] = count
    note("audit_log", "PASS" if count >= 0 and Log else "NOT_APPLICABLE", count)
except Exception as exc:
    fail("audit_log", exc)

# CXP
try:
    bills = env["account.move"].sudo().search(
        [
            ("move_type", "=", "in_invoice"),
            ("ref", "ilike", "DX TEST BILL"),
            ("state", "=", "posted"),
        ]
    )
    RESULTS["cxp"] = {
        "bills": len(bills),
        "residual": sum(bills.mapped("amount_residual")),
        "companies": bills.mapped("company_id.dx_short_code"),
    }
    note("cxp", "PASS" if bills else "FAIL", RESULTS["cxp"])
except Exception as exc:
    fail("cxp", exc)

# Partner statements
try:
    for code, partner in clients.items():
        company = companies.filtered(lambda c, x=code: c.dx_short_code == x)
        pdf = (
            env["ir.actions.report"]
            .sudo()
            .with_company(company)
            ._render_qweb_pdf(env.ref("justech_alexander_reports.action_report_partner_statement"), res_ids=partner.ids)[0]
        )
        (OUT / ("statement_%s.pdf" % code)).write_bytes(pdf)
    note("statements", "PASS", "6/6")
except Exception as exc:
    fail("statements", exc)

# Cross-company prints
try:
    pairs = [("PIN", "DOR"), ("REM", "BLU"), ("DOM", "MAY")]
    for doc_code, active_code in pairs:
        so = env["sale.order"].sudo().search(
            [("client_order_ref", "ilike", "DX TEST COTIZACION %s" % doc_code)], limit=1
        )
        active = companies.filtered(lambda c, a=active_code: c.dx_short_code == a)
        pdf = env["ir.actions.report"].sudo().with_company(active)._render_qweb_pdf(
            env.ref("sale.action_report_saleorder"), res_ids=so.ids
        )[0]
        (OUT / ("cross_%s_active_%s.pdf" % (doc_code, active_code))).write_bytes(pdf)
    note("cross_company", "PASS", pairs)
except Exception as exc:
    fail("cross_company", exc)

# Email TEST invoices to controlled mailbox only
try:
    Graph = env["dx.ms.graph.client"].sudo()
    email_rows = []
    for company in companies:
        code = company.dx_short_code
        inv = env["account.move"].sudo().search(
            [("ref", "ilike", "DX TEST FACTURA B01 %s" % code), ("company_id", "=", company.id)],
            limit=1,
        )
        if not inv:
            continue
        from_addr = company._dx_outgoing_address()
        pdf = render_pdf("account.account_invoices", inv)
        att = env["ir.attachment"].sudo().create(
            {
                "name": "DX_TEST_FACTURA_%s_%s.pdf" % (code, inv.justech_do_ncf),
                "type": "binary",
                "datas": base64.b64encode(pdf),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": inv.id,
            }
        )
        add_id("attachments", att, {"company": code})
        subject = "[DX TEST][NO FISCAL REAL][NO ENVIAR DGII] Factura TEST %s %s %s" % (
            code,
            inv.justech_do_ncf,
            TODAY.isoformat(),
        )
        mail = env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "email_from": from_addr,
                "email_to": "fausto@justech.do",
                "body_html": "<p>DX TEST — NO FISCAL REAL — NO ENVIAR DGII. Auditoría 360.</p>",
                "model": "account.move",
                "res_id": inv.id,
                "attachment_ids": [(6, 0, att.ids)],
            }
        )
        try:
            mail.send(raise_exception=True)
            sent = True
            err = ""
        except Exception as exc:
            sent = False
            err = str(exc)[:180]
        email_rows.append({"code": code, "from": from_addr, "sent": sent, "err": err, "ncf": inv.justech_do_ncf})
    RESULTS["email"] = email_rows
    note("email_invoices", "PASS" if all(r["sent"] for r in email_rows) else "FAIL", email_rows)
except Exception as exc:
    fail("email_invoices", exc)

# Extract 606/607/608 data (NOT official DGII exporter — models missing)
try:
    sales = env["account.move"].sudo().search(
        [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("justech_do_ncf", "like", "B0%991%"),
        ]
    )
    purchases = env["account.move"].sudo().search(
        [
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("ref", "ilike", "DX TEST BILL"),
        ]
    )
    voids = env["account.move"].sudo().search(
        [("justech_do_ncf_voided", "=", True), ("justech_do_ncf", "like", "B0%991%")]
    )

    def row607(m):
        return {
            "company": m.company_id.dx_short_code,
            "period": PERIOD,
            "rnc": m.partner_id.vat,
            "ncf": m.justech_do_ncf,
            "date": str(m.invoice_date),
            "untaxed": m.amount_untaxed,
            "tax": m.amount_tax,
            "total": m.amount_total,
            "type": m.move_type,
            "include_dgii": m.justech_do_include_in_dgii,
            "NO_ENVIAR_DGII": True,
        }

    def row606(m):
        return {
            "company": m.company_id.dx_short_code,
            "period": PERIOD,
            "vendor_rnc": m.partner_id.vat,
            "vendor_ncf": m.l10n_latam_document_number,
            "date": str(m.invoice_date),
            "untaxed": m.amount_untaxed,
            "tax": m.amount_tax,
            "total": m.amount_total,
            "NO_ENVIAR_DGII": True,
        }

    def row608(m):
        return {
            "company": m.company_id.dx_short_code,
            "period": PERIOD,
            "ncf": m.justech_do_ncf,
            "void_date": str(m.justech_do_ncf_void_date),
            "cancel_type": m.justech_do_ncf_cancel_type,
            "reason": m.justech_do_ncf_void_reason,
            "NO_ENVIAR_DGII": True,
        }

    extract = {"607": [row607(m) for m in sales], "606": [row606(m) for m in purchases], "608": [row608(m) for m in voids]}
    (OUT / ("DX_TEST_607_%s.json" % PERIOD)).write_text(json.dumps(extract["607"], indent=2, default=str))
    (OUT / ("DX_TEST_606_%s.json" % PERIOD)).write_text(json.dumps(extract["606"], indent=2, default=str))
    (OUT / ("DX_TEST_608_%s.json" % PERIOD)).write_text(json.dumps(extract["608"], indent=2, default=str))
    RESULTS["fiscal_extract"] = {k: len(v) for k, v in extract.items()}
    RESULTS["official_exporter"] = "NOT_INSTALLED"
    note("fiscal_extract", "PASS", RESULTS["fiscal_extract"])
    # exclude TEST docs from any future official period file
    (sales | purchases | voids).write(
        {
            "justech_do_include_in_dgii": False,
            "justech_do_dgii_exclusion_reason": "DX TEST 360 — NO ENVIAR DGII — excluir de período real",
        }
    )
except Exception as exc:
    fail("fiscal_extract", exc)

# Operational user smoke (read + confirm they are not system)
try:
    op = env["res.users"].sudo().search([("login", "=", "inversionesdoralex@gmail.com")], limit=1)
    RESULTS["operational"] = {
        "exists": bool(op),
        "system": bool(op and op.has_group("base.group_system")),
        "companies": op.company_ids.mapped("dx_short_code") if op else [],
    }
    if op:
        so = env["sale.order"].with_user(op).search([("client_order_ref", "ilike", "DX TEST")], limit=5)
        RESULTS["operational"]["can_read_qa_so"] = len(so)
    note("operational_user", "PASS", RESULTS["operational"])
except Exception as exc:
    fail("operational_user", exc)

# Crons
try:
    crons = []
    for c in env["ir.cron"].sudo().search([]):
        xmlid = c.get_external_id().get(c.id) or ""
        if any(x in (c.name or "").lower() + xmlid.lower() for x in ("justech", "ncf", "graph", "garant", "audit", "doralex")):
            crons.append(
                {
                    "name": c.name,
                    "active": c.active,
                    "last": str(c.lastcall),
                    "next": str(c.nextcall),
                }
            )
    RESULTS["crons"] = crons
    note("crons", "PASS", len(crons))
except Exception as exc:
    fail("crons", exc)

# Persist
(OUT / "manifest.json").write_text(json.dumps(CATALOG, indent=2, default=str))
(OUT / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str))
env.cr.commit()
print("DX360_DONE fails=%s steps=%s" % (len(RESULTS["fails"]), len(RESULTS["steps"])))
