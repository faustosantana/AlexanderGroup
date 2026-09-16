# -*- coding: utf-8 -*-
"""STAGING closeout UAT. Never Prod. Explicit commit at the end."""

from odoo.exceptions import AccessError, UserError

assert env.cr.dbname == "doralex_ent_staging"
results = []


def rec(name, ok, detail):
    results.append((name, "PASS" if ok else "FAIL", detail))
    print("UAT", name, "PASS" if ok else "FAIL", detail)


# --- versions / flags ---
def _mod(name):
    return env["ir.module.module"].sudo().search([("name", "=", name)], limit=1)


base = _mod("justech_alexander_base")
ux = _mod("justech_alexander_ux")
rec("OVERLAY_VERSIONS", base.latest_version == "19.0.1.0.7" and ux.latest_version == "19.0.1.6.0",
    "base=%s ux=%s" % (base.latest_version, ux.latest_version))

ops = env["res.company"].sudo().search([("id", "in", [8, 9, 10, 11, 12, 13])])
flags_off = all(
    not c.justech_approval_sale_enabled
    and not c.justech_approval_purchase_enabled
    and not c.justech_approval_invoice_enabled
    for c in ops
)
rec("H11_FLAGS_OFF", flags_off, "companies=%s" % len(ops))

cron = env.ref("justech_l10n_do_base.ir_cron_justech_rnc_padron_auto_update", raise_if_not_found=False)
rec("H09_CRON_OFF", bool(cron) and not cron.active, "cron=%s active=%s" % (cron and cron.id, cron and cron.active))
rec("H09_PADRON_ROWS", env["justech.do.rnc.padron"].sudo().search_count([]) == 0, "rows=%s" % env["justech.do.rnc.padron"].sudo().search_count([]))

Catalog = env["justech.do.withholding.catalog"].sudo().with_context(active_test=False)
codes = Catalog.search([("code", "like", "DX-")]).mapped("code")
need = {
    "DX-ISR-ESTADO-5",
    "DX-ISR-PROF-PF-15",
    "DX-ISR-TEC-PF-15",
    "DX-ITBIS-30-PJ",
    "DX-ITBIS-100-PF",
    "DX-ISR-EXT-REG-15",
}
rec("H13_CATALOG_CODES", need.issubset(set(codes)), "codes=%s" % sorted(codes))

cfg_ok = True
cfg_detail = []
for cid in (8, 11):
    for code in ("DX-ISR-PROF-PF-15", "DX-ITBIS-30-PJ", "DX-ITBIS-100-PF"):
        cat = Catalog.search([("code", "=", code)], limit=1)
        cfg = env["justech.do.withholding.company.config"].sudo().search(
            [("catalog_id", "=", cat.id), ("company_id", "=", cid)], limit=1
        )
        ok = bool(cfg and cfg.account_id and cfg.active_config)
        cfg_ok = cfg_ok and ok
        cfg_detail.append("%s@%s acc=%s" % (code, cid, cfg.account_id.display_name if cfg and cfg.account_id else None))
rec("H13_ACCOUNT_MAP", cfg_ok, "; ".join(cfg_detail))

# --- helpers ---
do = env.ref("base.do")
c11 = env["res.company"].browse(11)
c8 = env["res.company"].browse(8)
ctx11 = dict(env.context, allowed_company_ids=[11], mail_notrack=True, tracking_disable=True)
ctx8 = dict(env.context, allowed_company_ids=[8], mail_notrack=True, tracking_disable=True)
e11 = env(context=ctx11)
e8 = env(context=ctx8)


def sale_tax(e, company, amount):
    return e["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", amount),
            ("name", "ilike", "ITBIS"),
        ],
        limit=1,
    )


def purchase_tax(e, company, amount):
    return e["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "purchase"),
            ("amount", "=", amount),
            ("name", "ilike", "ITBIS"),
        ],
        limit=1,
    )


tax16 = e11["account.tax"].search(
    [("company_id", "=", 11), ("type_tax_use", "=", "sale"), ("amount", "=", 16)], limit=1
)
tax18s = sale_tax(e11, c11, 18)
tax18p = purchase_tax(e11, c11, 18)
tax18p8 = purchase_tax(e8, c8, 18)

ptn_sale = e11["res.partner"].search([("name", "=", "DXUAT CLIENTE PAGOS")], limit=1)
if not ptn_sale:
    ptn_sale = e11["res.partner"].create(
        {
            "name": "DXUAT CLIENTE PAGOS",
            "company_id": 11,
            "vat": "131000002",
            "is_company": True,
            "customer_rank": 1,
            "country_id": do.id,
        }
    )

# H11: quotation edit + confirm without approval
p_sale = e11["product.product"].search([("default_code", "=", "DXUAT-PAY")], limit=1)
if not p_sale:
    p_sale = e11["product.product"].create(
        {
            "name": "UAT Pago",
            "default_code": "DXUAT-PAY",
            "type": "service",
            "list_price": 1000,
            "company_id": 11,
            "taxes_id": [(6, 0, tax18s.ids)],
        }
    )
so = e11["sale.order"].create(
    {
        "partner_id": ptn_sale.id,
        "company_id": 11,
        "note": "H11 closeout",
        "order_line": [
            (
                0,
                0,
                {
                    "product_id": p_sale.id,
                    "product_uom_qty": 1,
                    "price_unit": 1000,
                    "discount": 0,
                    "tax_ids": [(6, 0, tax18s.ids)],
                },
            )
        ],
    }
)
line = so.order_line[0]
line.write({"product_uom_qty": 2, "price_unit": 1100, "discount": 5})
so.write({"note": "H11 terms edited", "client_order_ref": "H11-CLOSEOUT"})
blocked = False
try:
    so.action_confirm()
except UserError as exc:
    blocked = "aprob" in str(exc).lower() or "approval" in str(exc).lower()
    rec("H11_CONFIRM", False, str(exc))
else:
    rec(
        "H11_CONFIRM",
        so.state == "sale" and so.justech_approval_state in ("none", False, "approved"),
        "so=%s state=%s approval=%s" % (so.name, so.state, so.justech_approval_state),
    )

# H09: new partner pending_new must not block invoice
ptn_new = e11["res.partner"].search([("name", "=", "DXUAT PADRON FREE")], limit=1)
if not ptn_new:
    ptn_new = e11["res.partner"].create(
        {
            "name": "DXUAT PADRON FREE",
            "company_id": 11,
            "vat": "131000099",
            "is_company": True,
            "customer_rank": 1,
            "country_id": do.id,
        }
    )
rec(
    "H09_PARTNER_CREATE",
    ptn_new.justech_do_fiscal_config_state in ("pending_new", "not_applicable", "needs_review", "confirmed_history", "validated_padron"),
    "state=%s" % ptn_new.justech_do_fiscal_config_state,
)
so2 = e11["sale.order"].create(
    {
        "partner_id": ptn_new.id,
        "company_id": 11,
        "order_line": [
            (0, 0, {"product_id": p_sale.id, "product_uom_qty": 1, "price_unit": 100, "tax_ids": [(6, 0, tax18s.ids)]})
        ],
    }
)
so2.action_confirm()
try:
    inv_h09 = so2._create_invoices()[0]
    inv_h09.action_post()
    rec("H09_INVOICE_NO_PADRON", inv_h09.state == "posted", "inv=%s ncf=%s" % (inv_h09.name, inv_h09.justech_do_ncf if "justech_do_ncf" in inv_h09._fields else ""))
except Exception as exc:  # noqa: BLE001
    rec("H09_INVOICE_NO_PADRON", "padrón" not in str(exc).lower() and "pendiente de validar" not in str(exc).lower(), str(exc))
env.cr.commit()

# H04 sales-only user
Users = env["res.users"].sudo()
sales_login = "dxuat.sales.only@example.invalid"
sales_u = Users.with_context(active_test=False).search([("login", "=", sales_login)], limit=1)
sale_g = env.ref("sales_team.group_sale_salesman")
internal = env.ref("base.group_user")
purchase_g = env.ref("purchase.group_purchase_user")
if not sales_u:
    sales_u = Users.create(
        {
            "name": "DXUAT Solo Ventas",
            "login": sales_login,
            "email": sales_login,
            "company_id": 11,
            "company_ids": [(6, 0, [11])],
            "group_ids": [(6, 0, [internal.id, sale_g.id])],
        }
    )
else:
    sales_u.write({"group_ids": [(6, 0, [internal.id, sale_g.id])], "active": True})
rec(
    "H04_SALES_GROUPS",
    sales_u.has_group("sales_team.group_sale_salesman") and not sales_u.has_group("purchase.group_purchase_user"),
    "groups=%s" % sales_u.group_ids.mapped("name"),
)
so_own = False
try:
    so_own = (
        e11["sale.order"]
        .with_user(sales_u)
        .with_company(c11)
        .create(
            {
                "partner_id": ptn_sale.id,
                "company_id": 11,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": p_sale.id,
                            "product_uom_qty": 1,
                            "price_unit": 250,
                            "tax_ids": [(6, 0, tax18s.ids)],
                        },
                    )
                ],
            }
        )
    )
    rec("H04_SALES_CAN_READ_SO", bool(so_own.name), so_own.name)
except Exception as exc:  # noqa: BLE001
    rec("H04_SALES_CAN_READ_SO", False, str(exc)[:160])
rec("H04_SALES_NO_PURCHASE", not sales_u.has_group("purchase.group_purchase_user"), "ok")
rec("H04_SALES_NO_STOCK_ADMIN", not sales_u.has_group("stock.group_stock_manager"), "ok")
rec("H04_SALES_NO_ACCOUNT_ADMIN", not sales_u.has_group("account.group_account_manager"), "ok")
sales_u.write({"active": False})
rec("H04_DEACTIVATED", not sales_u.active, sales_u.login)
env.cr.commit()

# H07 draft cancel / unlink
inv_g = env.ref("account.group_account_invoice")
recov_g = env.ref("justech_accounting_recovery.group_accounting_recovery")
bill_login = "dxuat.billing@example.invalid"
bill_u = Users.with_context(active_test=False).search([("login", "=", bill_login)], limit=1)
if not bill_u:
    bill_u = Users.create(
        {
            "name": "DXUAT Facturacion",
            "login": bill_login,
            "email": bill_login,
            "company_id": 11,
            "company_ids": [(6, 0, [11])],
            "group_ids": [(6, 0, [internal.id, inv_g.id])],
        }
    )
else:
    bill_u.write({"group_ids": [(6, 0, [internal.id, inv_g.id])], "active": True})

journal = e11["account.journal"].search([("company_id", "=", 11), ("type", "=", "sale")], limit=1)
draft = e11["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": ptn_sale.id,
        "company_id": 11,
        "journal_id": journal.id,
        "invoice_line_ids": [
            (0, 0, {"name": "draft cancel", "quantity": 1, "price_unit": 10, "tax_ids": [(6, 0, tax18s.ids)]})
        ],
    }
)
try:
    draft.with_user(bill_u).with_company(c11).button_cancel()
    rec("H07_DRAFT_CANCEL", draft.state == "cancel", "state=%s" % draft.state)
except Exception as exc:  # noqa: BLE001
    rec("H07_DRAFT_CANCEL", False, str(exc))

draft2 = e11["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": ptn_sale.id,
        "company_id": 11,
        "journal_id": journal.id,
        "invoice_line_ids": [
            (0, 0, {"name": "draft unlink", "quantity": 1, "price_unit": 10, "tax_ids": [(6, 0, tax18s.ids)]})
        ],
    }
)
did = draft2.id
try:
    draft2.with_user(bill_u).with_company(c11).unlink()
    rec("H07_DRAFT_UNLINK", not e11["account.move"].browse(did).exists(), "deleted")
except Exception as exc:  # noqa: BLE001
    rec("H07_DRAFT_UNLINK", False, str(exc))

posted = e11["account.move"].search([("name", "=", "INV/2026/00067")], limit=1)
if posted and posted.state == "posted":
    try:
        posted.with_user(bill_u).with_company(c11).button_draft()
        rec("H07_POSTED_RESET_BILLING", False, "unexpectedly allowed")
        posted.action_post()
    except AccessError as exc:
        rec("H07_POSTED_RESET_BILLING", True, "blocked: %s" % str(exc)[:80])
    except Exception as exc:  # noqa: BLE001
        rec("H07_POSTED_RESET_BILLING", "recuperaci" in str(exc).lower() or "recovery" in str(exc).lower(), str(exc)[:120])
else:
    rec("H07_POSTED_RESET_BILLING", False, "INV/2026/00067 missing")

# H01 credit note 16%
inv16 = e11["account.move"].search([("name", "=", "INV/2026/00067")], limit=1)
try:
    cn = e11["account.move"].search(
        [("reversed_entry_id", "=", inv16.id), ("move_type", "=", "out_refund")],
        order="id desc",
        limit=1,
    )
    if not cn:
        Reversal = e11["account.move.reversal"]
        wiz_vals = {"reason": "UAT H01 CN ITBIS 16"}
        if "journal_id" in Reversal._fields:
            wiz_vals["journal_id"] = inv16.journal_id.id
        wiz = Reversal.with_context(active_model="account.move", active_ids=inv16.ids, active_id=inv16.id).create(wiz_vals)
        action = wiz.reverse_moves()
        if isinstance(action, dict) and action.get("res_id"):
            cn = e11["account.move"].browse(action["res_id"])
        else:
            cn = e11["account.move"].search(
                [("reversed_entry_id", "=", inv16.id), ("move_type", "=", "out_refund")],
                order="id desc",
                limit=1,
            )
    if cn and cn.state == "draft":
        try:
            cn.action_post()
        except Exception as exc:  # noqa: BLE001
            print("H01_CN_POST_WARN", exc)
    rec(
        "H01_CREDIT_NOTE",
        cn
        and abs(cn.amount_untaxed) == 1000
        and abs(cn.amount_tax) == 160
        and abs(cn.amount_total) == 1160,
        "cn=%s untaxed=%s tax=%s total=%s state=%s" % (cn.name if cn else None, cn.amount_untaxed if cn else None, cn.amount_tax if cn else None, cn.amount_total if cn else None, cn.state if cn else None),
    )
except Exception as exc:  # noqa: BLE001
    rec("H01_CREDIT_NOTE", False, str(exc))
env.cr.commit()

# H13 compute on dummy vendor moves (may stay draft if NCF blocks post)
def _vendor_bill(e, company, partner, tax, price, name):
    j = e["account.journal"].search([("company_id", "=", company.id), ("type", "=", "purchase")], limit=1)
    return e["account.move"].create(
        {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "company_id": company.id,
            "journal_id": j.id,
            "invoice_date": "2026-09-16",
            "invoice_line_ids": [
                (0, 0, {"name": name, "quantity": 1, "price_unit": price, "tax_ids": [(6, 0, tax.ids)]})
            ],
        }
    )


pf = e11["res.partner"].search([("name", "=", "DXUAT PROV PF")], limit=1)
if not pf:
    pf = e11["res.partner"].create(
        {
            "name": "DXUAT PROV PF",
            "company_id": 11,
            "is_company": False,
            "vat": "00100000012",
            "supplier_rank": 1,
            "country_id": do.id,
        }
    )
pj = e11["res.partner"].search([("name", "=", "DXUAT PROV PJ")], limit=1)
if not pj:
    pj = e11["res.partner"].create(
        {
            "name": "DXUAT PROV PJ",
            "company_id": 11,
            "is_company": True,
            "vat": "131000088",
            "supplier_rank": 1,
            "country_id": do.id,
        }
    )

bill_pf = _vendor_bill(e11, c11, pf, tax18p, 100000, "H13 PF prof")
bill_pj = _vendor_bill(e11, c11, pj, tax18p, 100000, "H13 PJ 30")
bill_tec = _vendor_bill(e11, c11, pf, tax18p, 100000, "H13 PF tec")
bill_gov = _vendor_bill(e11, c11, pj, tax18p, 100000, "H13 estado")
pj8 = e8["res.partner"].search([("name", "=", "DXUAT PROV PJ BLU")], limit=1)
if not pj8:
    pj8 = e8["res.partner"].create(
        {
            "name": "DXUAT PROV PJ BLU",
            "company_id": 8,
            "is_company": True,
            "vat": "131000077",
            "supplier_rank": 1,
            "country_id": do.id,
        }
    )
bill8 = _vendor_bill(e8, c8, pj8, tax18p8, 100000, "H13 co8")

prof = Catalog.search([("code", "=", "DX-ISR-PROF-PF-15")], limit=1)
tec = Catalog.search([("code", "=", "DX-ISR-TEC-PF-15")], limit=1)
it30 = Catalog.search([("code", "=", "DX-ITBIS-30-PJ")], limit=1)
it100 = Catalog.search([("code", "=", "DX-ITBIS-100-PF")], limit=1)
gov = Catalog.search([("code", "=", "DX-ISR-ESTADO-5")], limit=1)

rec("H13_ISR_PROF", abs(prof.compute_withholding_amount(bill_pf) - 15000) < 0.01, prof.compute_withholding_amount(bill_pf))
rec("H13_ISR_TEC", abs(tec.compute_withholding_amount(bill_tec) - 3000) < 0.01, tec.compute_withholding_amount(bill_tec))
rec("H13_ITBIS_30", abs(it30.compute_withholding_amount(bill_pj) - 5400) < 0.01, it30.compute_withholding_amount(bill_pj))
rec("H13_ITBIS_100", abs(it100.compute_withholding_amount(bill_pf) - 18000) < 0.01, it100.compute_withholding_amount(bill_pf))
rec("H13_GOV_5", abs(gov.compute_withholding_amount(bill_gov) - 5000) < 0.01, gov.compute_withholding_amount(bill_gov))
rec("H13_MULTI", abs((prof.compute_withholding_amount(bill_pf) + it100.compute_withholding_amount(bill_pf)) - 33000) < 0.01, "85000 neto expected")
rec("H13_CO8_ITBIS30", abs(it30.compute_withholding_amount(bill8) - 5400) < 0.01, it30.compute_withholding_amount(bill8))
rec("H13_PARTIAL", abs(it30.compute_withholding_amount(bill_pj, applied_amount=59000) - 2700) < 0.01, it30.compute_withholding_amount(bill_pj, applied_amount=59000))

# Try posting one vendor bill + payment with selected withholdings
posted_wh = False
try:
    bill_pf.action_post()
    posted_wh = bill_pf.state == "posted"
    rec("H13_BILL_POST", posted_wh, "state=%s residual=%s" % (bill_pf.state, bill_pf.amount_residual))
except Exception as exc:  # noqa: BLE001
    rec("H13_BILL_POST", False, str(exc)[:200])

if posted_wh:
    try:
        journal_bank = e11["account.journal"].search([("company_id", "=", 11), ("type", "=", "bank")], limit=1)
        pml = e11["account.payment.method.line"].search(
            [("journal_id", "=", journal_bank.id), ("payment_type", "=", "outbound")], limit=1
        )
        Wiz = e11["justech.payment.partner.wizard"]
        wiz = Wiz.with_context(
            active_model="account.move",
            active_ids=bill_pf.ids,
            justech_preselect_move_ids=bill_pf.ids,
            allowed_company_ids=[11],
        ).create(
            {
                "partner_id": pf.id,
                "partner_type": "supplier",
                "journal_id": journal_bank.id,
                "payment_method_line_id": pml.id if pml else False,
                "currency_id": bill_pf.currency_id.id,
            }
        )
        line = wiz.line_ids.filtered(lambda l: l.move_id == bill_pf)
        line.write(
            {
                "apply": True,
                "amount_to_pay": bill_pf.amount_residual,
                "withholding_catalog_ids": [(6, 0, [prof.id, it100.id])],
            }
        )
        line._recompute_line_withholdings()
        rec(
            "H13_WIZARD_AMOUNTS",
            abs(line.withholding_amount - 33000) < 0.5 and abs(line.net_after_withholding - 85000) < 0.5,
            "wh=%s net=%s details=%s" % (line.withholding_amount, line.net_after_withholding, line.withholding_detail_ids.mapped("amount")),
        )
        if hasattr(wiz, "action_register"):
            wiz.action_register()
        elif hasattr(wiz, "action_create_payments"):
            wiz.action_create_payments()
        bill_pf.invalidate_recordset()
        rec("H13_PAYMENT", bill_pf.amount_residual == 0, "residual=%s payment_state=%s" % (bill_pf.amount_residual, bill_pf.payment_state))
    except Exception as exc:  # noqa: BLE001
        rec("H13_PAYMENT", False, str(exc)[:240])

# CN on 18% sale invoice for tax compare
inv18 = e11["account.move"].search([("name", "=", "INV/2026/00068")], limit=1)
if inv18:
    rec("H01_18_COMPARE", abs(inv18.amount_tax / inv18.amount_untaxed - 0.18) < 0.001, "tax=%s base=%s" % (inv18.amount_tax, inv18.amount_untaxed))

print("=== MATRIX ===")
for name, status, detail in results:
    print("%s\t%s\t%s" % (name, status, detail))
fails = [n for n, s, _ in results if s != "PASS"]
print("FAILS", fails)
env.cr.commit()
print("COMMITTED")
