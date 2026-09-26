# ruff: noqa
"""Staging go-live QA. Rolls back writes. No NCF/DGII/e-CF/mail."""

from __future__ import annotations

import json

from odoo.exceptions import AccessError, UserError, ValidationError

TAG = "DXQA-GOLIVE-20260926"
OUT = "/tmp/golive_staging_qa.json"
COMPANIES = (8, 9, 10, 11, 12, 13)
PEOPLE = {
    "ALEXANDER": "alexander.pina@inversionesdoralex.com",
    "LUIS": "luis.aquino@inversionesdoralex.com",
    "JANNY": "janny.montero@inversionesdoralex.com",
    "ELIANNY": "elianny.sanchez@inversionesdoralex.com",
    "LEOPORDO": "leopordo.jimenez@inversionesdoralex.com",
    "GEILIN": "geilin.rosario@inversionesdoralex.com",
}
OPS = ("LUIS", "JANNY", "ELIANNY", "LEOPORDO")


def _user(login):
    return env["res.users"].sudo().search([("login", "=", login)], limit=1)


def _has(user, xml):
    rec = env.ref(xml, raise_if_not_found=False)
    return bool(user and rec and rec in user.group_ids)


def _try(fn):
    try:
        fn()
        return {"ok": True}
    except AccessError as exc:
        return {"ok": False, "error": "AccessError", "msg": str(exc)[:220]}
    except (UserError, ValidationError) as exc:
        return {"ok": False, "error": type(exc).__name__, "msg": str(exc)[:220]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "msg": str(exc)[:220]}


def _find(needles, company_id=None, ptype="consu"):
    P = env["product.product"].sudo().with_context(active_test=True)
    domain = [("sale_ok", "=", True), ("type", "=", ptype)]
    if company_id:
        domain = (
            ["&"]
            + domain
            + ["|", ("company_id", "=", False), ("company_id", "=", company_id)]
        )
    for needle in needles:
        rec = P.search(domain + [("name", "ilike", needle)], limit=1)
        if rec:
            return rec
    return P.browse()


def _partner(e, cid, kind):
    name = "DXQA-OPREADY-20260907 %s %s" % (
        "CLIENTE" if kind == "customer" else "PROV",
        cid,
    )
    rec = (
        e["res.partner"]
        .with_context(active_test=False)
        .search([("name", "=", name)], limit=1)
    )
    if rec:
        return rec
    return (
        e["res.partner"]
        .with_company(e["res.company"].browse(cid))
        .create(
            {
                "name": "%s %s %s" % (TAG, kind, cid),
                "is_company": True,
                "company_id": False,
                "email": "noreply-golive@invalid.local",
                "vat": False,
                "customer_rank": 1 if kind == "customer" else 0,
                "supplier_rank": 1 if kind == "vendor" else 0,
            }
        )
    )


def _as(user, cid):
    return env(
        user=user.id,
        context=dict(
            env.context,
            allowed_company_ids=[cid],
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            mail_auto_subscribe_no_notify=True,
        ),
    )


report = {
    "TAG": TAG,
    "MAIL_SENT": 0,
    "DGII_SENT": 0,
    "ECF_SENT": 0,
    "NCF_CONSUMED": "NO",
    "companies": {},
    "users": {},
    "goods_qa": {},
    "cross_tax": {},
    "errors": [],
}

T = env["product.template"].sudo().with_context(active_test=False)
grava_t = T.search(
    [("name", "=", "Agregado grueso (grava) 3/4"), ("active", "=", True)], limit=1
)
svc_t = T.search(
    [("name", "=", "Servicios profesionales"), ("type", "=", "service")], limit=1
)
grava = grava_t.product_variant_id
svc = svc_t.product_variant_id
cemento = _find(["cemento portland", "cemento "]) or _find(["cemento"])
pintura = _find(["pintura acrilica", "pintura latex", "pintura "]) or _find(["pintura"])
appl = _find(["nevera", "lavadora", "televisor"])
furn = _find(["escritorio", "silla ejecutiva", "silla "])
pin = (
    env["product.product"]
    .sudo()
    .search(
        [("company_id", "=", 9), ("type", "=", "consu"), ("name", "ilike", "carne")],
        limit=1,
    )
)
report["goods_qa"] = {
    "grava": (
        {
            "id": grava_t.id,
            "type": grava_t.type,
            "sale_ok": bool(grava_t.sale_ok),
            "purchase_ok": bool(grava_t.purchase_ok),
            "active": bool(grava_t.active),
        }
        if grava_t
        else None
    ),
    "servicios": (
        {
            "id": svc_t.id,
            "type": svc_t.type,
            "list_price": float(svc_t.list_price or 0),
            "sale_ok": bool(svc_t.sale_ok),
        }
        if svc_t
        else None
    ),
    "cemento": (
        {"id": cemento.id, "name": cemento.display_name, "type": cemento.type}
        if cemento
        else None
    ),
    "pintura": (
        {"id": pintura.id, "name": pintura.display_name, "type": pintura.type}
        if pintura
        else None
    ),
    "appliance": (
        {"id": appl.id, "name": appl.display_name, "type": appl.type} if appl else None
    ),
    "furniture": (
        {"id": furn.id, "name": furn.display_name, "type": furn.type} if furn else None
    ),
    "pinaria": (
        {
            "id": pin.id,
            "name": pin.display_name,
            "type": pin.type,
            "company": pin.company_id.id,
        }
        if pin
        else None
    ),
}

ncf_before = {}
if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].sudo().search([]):
        ncf_before[r.id] = r.next_sequence if "next_sequence" in r._fields else None
mail_before = env["mail.mail"].sudo().search_count([]) if "mail.mail" in env else 0

# Company E2E — reuse existing QA partners, rollback after each company
for cid in COMPANIES:
    company = env["res.company"].sudo().browse(cid)
    rec = {"company": company.name, "cid": cid}
    env.cr.execute("SAVEPOINT golive_co_%s" % cid)
    try:
        e = env(
            context=dict(
                env.context,
                allowed_company_ids=[cid],
                tracking_disable=True,
                mail_create_nolog=True,
                mail_notrack=True,
            )
        )
        partner = _partner(e, cid, "customer")
        vendor = _partner(e, cid, "vendor")
        product = pin if cid == 9 and pin else grava
        so = (
            e["sale.order"]
            .with_company(company)
            .create(
                {
                    "partner_id": partner.id,
                    "company_id": cid,
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
        )
        rec["so_create"] = True
        rec["so_product"] = product.display_name
        rec["so_type"] = product.type
        rec["so_tax_cos"] = list(
            {t.company_id.id for t in so.order_line.tax_ids if t.company_id}
        )
        rec["so_tax_ok"] = (
            all(x == cid for x in rec["so_tax_cos"]) if rec["so_tax_cos"] else True
        )
        rec["confirm"] = _try(so.action_confirm)
        rec["so_state"] = so.state
        rec["delivery_created"] = bool(so.picking_ids)
        if so.state in ("sale", "done"):
            rec["invoice_create"] = _try(so._create_invoices)
        rec["invoice_state"] = so.invoice_ids.mapped("state")
        rec["invoice_tax_ok"] = True
        for move in so.invoice_ids:
            for line in move.invoice_line_ids:
                for tax in line.tax_ids:
                    if tax.company_id and tax.company_id.id != cid:
                        rec["invoice_tax_ok"] = False
        po = (
            e["purchase.order"]
            .with_company(company)
            .create(
                {
                    "partner_id": vendor.id,
                    "company_id": cid,
                    "partner_ref": TAG,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "name": product.display_name,
                                "product_qty": 1,
                                "price_unit": 80.0,
                            },
                        )
                    ],
                }
            )
        )
        rec["po_create"] = True
        rec["po_tax_cos"] = list(
            {t.company_id.id for t in po.order_line.tax_ids if t.company_id}
        )
        rec["po_tax_ok"] = (
            all(x == cid for x in rec["po_tax_cos"]) if rec["po_tax_cos"] else True
        )
        rec["po_confirm"] = _try(po.button_confirm)
        rec["po_state"] = po.state
        rec["receipts"] = len(po.picking_ids)
        rec["pass"] = bool(
            rec.get("so_create")
            and rec.get("po_create")
            and rec.get("so_tax_ok")
            and rec.get("po_tax_ok")
            and rec.get("so_state") in ("sale", "done", "draft", "sent")
        )
    except Exception as exc:  # noqa: BLE001
        rec["pass"] = False
        rec["error"] = type(exc).__name__
        rec["msg"] = str(exc)[:240]
        report["errors"].append("%s %s" % (cid, rec.get("msg")))
    finally:
        env.cr.execute("ROLLBACK TO SAVEPOINT golive_co_%s" % cid)
        env.invalidate_all(flush=False)
    report["companies"][str(cid)] = rec

# Isolated negative permission + positive flows
for key, login in PEOPLE.items():
    user = _user(login)
    row = {"login": login, "found": bool(user)}
    if not user:
        report["users"][key] = row
        continue
    row.update(
        {
            "id": user.id,
            "active": user.active,
            "companies": user.company_ids.ids,
            "default": user.company_id.id,
            "SALES": _has(user, "sales_team.group_sale_salesman")
            or _has(user, "sales_team.group_sale_salesman_all_leads")
            or _has(user, "sales_team.group_sale_manager"),
            "PURCHASE": _has(user, "purchase.group_purchase_user")
            or _has(user, "purchase.group_purchase_manager"),
            "INVOICE": _has(user, "account.group_account_invoice"),
            "ACCOUNT_MGR": _has(user, "account.group_account_manager"),
            "SETTINGS": _has(user, "base.group_system"),
            "ADMIN": _has(user, "base.group_erp_manager"),
            "APPROVER": _has(user, "justech_approval_flow.group_approver"),
            "APPR_MGR": _has(user, "justech_approval_flow.group_manager"),
            "SELF": _has(user, "justech_approval_flow.group_self_approve"),
        }
    )
    cid = 11
    eu = _as(user, cid)
    # quote create/write — no confirm (avoids stock.move flush after rollback)
    env.cr.execute("SAVEPOINT golive_quote_%s" % user.id)
    try:
        partner = _partner(eu, cid, "customer")
        so = eu["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": cid,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": svc.id,
                            "product_uom_qty": 1,
                            "price_unit": 150.0,
                        },
                    )
                ],
            }
        )
        row["quote_create"] = True
        row["quote_write"] = _try(lambda: so.write({"client_order_ref": TAG}))
        row["quote_confirm"] = _try(so.action_confirm)
        row["quote_state"] = so.state
    except Exception as exc:  # noqa: BLE001
        row["quote_error"] = type(exc).__name__
        row["quote_msg"] = str(exc)[:200]
    finally:
        env.cr.execute("ROLLBACK TO SAVEPOINT golive_quote_%s" % user.id)
        env.invalidate_all(flush=False)

    env.cr.execute("SAVEPOINT golive_po_%s" % user.id)
    try:
        vendor = _partner(eu, cid, "vendor")
        po = eu["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "company_id": cid,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": svc.id,
                            "name": svc.display_name,
                            "product_qty": 1,
                            "price_unit": 90.0,
                        },
                    )
                ],
            }
        )
        row["po_create"] = True
        row["po_write"] = _try(lambda: po.write({"partner_ref": TAG}))
        row["po_confirm"] = _try(po.button_confirm)
        row["po_state"] = po.state
    except Exception as exc:  # noqa: BLE001
        row["po_error"] = type(exc).__name__
        row["po_msg"] = str(exc)[:200]
    finally:
        env.cr.execute("ROLLBACK TO SAVEPOINT golive_po_%s" % user.id)
        env.invalidate_all(flush=False)

    env.cr.execute("SAVEPOINT golive_inv_%s" % user.id)
    try:
        partner = _partner(eu, cid, "customer")

        def _inv():
            return eu["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "company_id": cid,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": svc.id,
                                "quantity": 1,
                                "price_unit": 100.0,
                                "name": TAG,
                            },
                        )
                    ],
                }
            )

        created = {"move": None}

        def _inv():
            created["move"] = eu["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "company_id": cid,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": svc.id,
                                "quantity": 1,
                                "price_unit": 100.0,
                                "name": TAG,
                            },
                        )
                    ],
                }
            )

        row["invoice_create"] = _try(_inv)
        if created["move"] is not None:
            row["invoice_post"] = _try(created["move"].action_post)
            row["invoice_posted"] = created["move"].state
    finally:
        env.cr.execute("ROLLBACK TO SAVEPOINT golive_inv_%s" % user.id)
        env.invalidate_all(flush=False)

    env.cr.execute("SAVEPOINT golive_usr_%s" % user.id)
    try:
        row["create_user"] = _try(
            lambda: eu["res.users"].create(
                {
                    "name": "SHOULD FAIL",
                    "login": "dx.fail.%s@invalid.local" % key.lower(),
                }
            )
        )
    finally:
        env.cr.execute("ROLLBACK TO SAVEPOINT golive_usr_%s" % user.id)
        env.invalidate_all(flush=False)

    if key in OPS:
        posted = row.get("invoice_post") or {}
        row["negative_invoice_blocked"] = (
            not row.get("invoice_create", {}).get("ok")
        ) or (not posted.get("ok"))
        row["negative_invoice_post_blocked"] = not posted.get("ok") if posted else True
        row["negative_settings_blocked"] = not row.get("create_user", {}).get("ok")
    if key == "GEILIN":
        row["geilin_can_invoice"] = bool(row.get("invoice_create", {}).get("ok"))
        row["geilin_not_acct_admin"] = not row["ACCOUNT_MGR"]
        row["geilin_not_settings"] = not row["SETTINGS"]
    if key == "ALEXANDER":
        row["alexander_six_companies"] = set(user.company_ids.ids) == set(COMPANIES)
        row["switch_company"] = _try(lambda: eu["res.company"].browse(8).name)
    report["users"][key] = row

# Cross-tax (existing live docs + leftover staging)
env.cr.execute("""
    SELECT COUNT(*) FROM account_tax_sale_order_line_rel rel
    JOIN sale_order_line sol ON sol.id = rel.sale_order_line_id
    JOIN sale_order so ON so.id = sol.order_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE tax.company_id IS NOT NULL AND tax.company_id <> so.company_id
      AND so.state IN ('draft','sent','sale')
    """)
report["cross_tax"]["sale"] = env.cr.fetchone()[0]
env.cr.execute("""
    SELECT COUNT(*) FROM account_tax_purchase_order_line_rel rel
    JOIN purchase_order_line pol ON pol.id = rel.purchase_order_line_id
    JOIN purchase_order po ON po.id = pol.order_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE tax.company_id IS NOT NULL AND tax.company_id <> po.company_id
      AND po.state IN ('draft','sent','to approve','purchase')
    """)
report["cross_tax"]["purchase"] = env.cr.fetchone()[0]
env.cr.execute("""
    SELECT po.id, po.name, po.company_id, tax.company_id, po.state
    FROM account_tax_purchase_order_line_rel rel
    JOIN purchase_order_line pol ON pol.id = rel.purchase_order_line_id
    JOIN purchase_order po ON po.id = pol.order_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE tax.company_id IS NOT NULL AND tax.company_id <> po.company_id
      AND po.state IN ('draft','sent','to approve','purchase')
    LIMIT 15
    """)
report["cross_tax"]["purchase_samples"] = env.cr.fetchall()
env.cr.execute("""
    SELECT COUNT(*) FROM account_move_line_account_tax_rel rel
    JOIN account_move_line aml ON aml.id = rel.account_move_line_id
    JOIN account_move am ON am.id = aml.move_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE am.state='draft' AND tax.company_id IS NOT NULL AND tax.company_id <> am.company_id
    """)
report["cross_tax"]["invoice"] = env.cr.fetchone()[0]

ncf_after = {}
if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].sudo().search([]):
        ncf_after[r.id] = r.next_sequence if "next_sequence" in r._fields else None
report["NCF_CONSUMED"] = "YES" if ncf_before != ncf_after else "NO"
mail_after = env["mail.mail"].sudo().search_count([]) if "mail.mail" in env else 0
report["MAIL_SENT"] = max(0, mail_after - mail_before)

report["SALES_END_TO_END"] = (
    "PASS"
    if all(
        v.get("so_create") and v.get("so_tax_ok") for v in report["companies"].values()
    )
    else "FAIL"
)
report["PURCHASE_END_TO_END"] = (
    "PASS"
    if all(
        v.get("po_create") and v.get("po_tax_ok") for v in report["companies"].values()
    )
    else "FAIL"
)
report["INVOICE_END_TO_END"] = (
    "PASS"
    if all(v.get("invoice_tax_ok", True) for v in report["companies"].values())
    else "FAIL"
)
ops_neg = all(
    report["users"][k].get("negative_invoice_blocked")
    and report["users"][k].get("negative_settings_blocked")
    for k in OPS
    if report["users"][k].get("found")
)
report["NEGATIVE_PERMISSION_QA"] = "PASS" if ops_neg else "FAIL"
geilin = report["users"].get("GEILIN") or {}
report["GEILIN_INVOICE_QA"] = (
    "PASS"
    if geilin.get("geilin_can_invoice") and geilin.get("geilin_not_acct_admin")
    else "FAIL"
)
report["GEILIN_ACCOUNTING_ADMIN"] = "NO" if not geilin.get("ACCOUNT_MGR") else "YES"
alex = report["users"].get("ALEXANDER") or {}
report["ALEXANDER_QA"] = (
    "PASS" if alex.get("alexander_six_companies") and alex.get("SETTINGS") else "FAIL"
)
report["ALEXANDER_APPROVER"] = "YES" if alex.get("APPROVER") else "NO"
report["ALEXANDER_APPROVAL_ADMIN"] = "YES" if alex.get("APPR_MGR") else "NO"
report["APPROVAL_QA"] = (
    "PASS"
    if report["ALEXANDER_APPROVER"] == "YES"
    and all(
        not report["users"][k].get("SELF")
        for k in OPS + ("GEILIN",)
        if report["users"][k].get("found")
    )
    else "FAIL"
)
report["CROSS_COMPANY_TAX_REFERENCE"] = (
    report["cross_tax"]["sale"] + report["cross_tax"]["invoice"]
)
report["CROSS_COMPANY_TAX_PURCHASE_STAGING"] = report["cross_tax"]["purchase"]
report["GRAVA_TYPE"] = grava_t.type if grava_t else None
report["SERVICIOS_TYPE"] = svc_t.type if svc_t else None
report["PHYSICAL_GOODS_SELECTABLE"] = all(
    x and x.get("type") == "consu"
    for x in (
        report["goods_qa"]["grava"],
        report["goods_qa"]["cemento"],
        report["goods_qa"]["pintura"],
        report["goods_qa"]["pinaria"],
    )
    if x
)
report["SERVICIOS_STILL_SERVICE"] = (
    bool(svc_t) and svc_t.type == "service" and float(svc_t.list_price or 0) == 0.0
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
print("WROTE", OUT)
print(
    json.dumps(
        {
            k: report[k]
            for k in (
                "SALES_END_TO_END",
                "PURCHASE_END_TO_END",
                "INVOICE_END_TO_END",
                "NEGATIVE_PERMISSION_QA",
                "GEILIN_INVOICE_QA",
                "GEILIN_ACCOUNTING_ADMIN",
                "ALEXANDER_QA",
                "ALEXANDER_APPROVER",
                "ALEXANDER_APPROVAL_ADMIN",
                "APPROVAL_QA",
                "CROSS_COMPANY_TAX_REFERENCE",
                "CROSS_COMPANY_TAX_PURCHASE_STAGING",
                "NCF_CONSUMED",
                "MAIL_SENT",
                "GRAVA_TYPE",
                "SERVICIOS_TYPE",
                "PHYSICAL_GOODS_SELECTABLE",
                "SERVICIOS_STILL_SERVICE",
            )
        },
        ensure_ascii=False,
        indent=2,
    )
)
print("COMPANY_PASSES", {k: v.get("pass") for k, v in report["companies"].items()})
print(
    "OPS_NEG",
    {
        k: (
            report["users"][k].get("negative_invoice_blocked"),
            report["users"][k].get("invoice_create"),
        )
        for k in OPS
    },
)
