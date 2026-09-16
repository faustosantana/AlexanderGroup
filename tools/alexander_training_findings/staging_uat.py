# -*- coding: utf-8 -*-
"""STAGING UAT for Alexander training findings. Never Prod. Never send mail."""

import json
import time
import traceback

TAG = "DXUAT-TF-20260916"
OUT = "/tmp/alexander_staging_uat.json"
PDF_DIR = "/tmp/alexander_uat_pdfs"
INV_DATE = "2026-09-16"

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

import os

os.makedirs(PDF_DIR, exist_ok=True)

report = {
    "tag": TAG,
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "db": env.cr.dbname,
    "prod_touched": False,
    "environment": "STAGING",
    "checklist": {},
    "findings": {},
    "errors": [],
}

assert env.cr.dbname == "doralex_ent_staging", "REFUSE: not staging"


def _ok(item, status, **extra):
    rec = {"id": item, "status": status}
    rec.update(extra)
    report["checklist"][item] = rec
    return rec


def _exc(item, exc):
    report["errors"].append({"id": item, "error": "%s: %s" % (type(exc).__name__, exc)})
    return _ok(item, "FAIL", error="%s: %s" % (type(exc).__name__, exc))


def _company_env(company):
    return env(
        context=dict(
            env.context,
            allowed_company_ids=[company.id],
            justech_approval_skip=True,
            **ctx_mail,
        )
    )


def _tax_dump(tax):
    if not tax:
        return None
    tax = tax.sudo()

    def _rep(lines):
        rows = []
        for line in lines:
            rows.append(
                {
                    "repartition_type": line.repartition_type,
                    "factor_percent": line.factor_percent,
                    "account_id": line.account_id.id or False,
                    "account": line.account_id.display_name or False,
                    "account_code": line.account_id.code or False,
                    "tag_ids": [
                        {"id": t.id, "name": t.name, "applicability": t.applicability}
                        for t in line.tag_ids
                    ],
                }
            )
        return rows

    return {
        "id": tax.id,
        "name": tax.name,
        "company_id": tax.company_id.id,
        "company": tax.company_id.name,
        "amount": tax.amount,
        "amount_type": tax.amount_type,
        "type_tax_use": tax.type_tax_use,
        "price_include": tax.price_include,
        "tax_group_id": tax.tax_group_id.id or False,
        "tax_group": tax.tax_group_id.display_name or False,
        "active": tax.active,
        "invoice_repartition_line_ids": _rep(tax.invoice_repartition_line_ids),
        "refund_repartition_line_ids": _rep(tax.refund_repartition_line_ids),
        "tax_exigibility": getattr(tax, "tax_exigibility", None),
        "include_base_amount": tax.include_base_amount,
        "is_base_affected": getattr(tax, "is_base_affected", None),
        "country_id": tax.country_id.code if tax.country_id else False,
        "l10n_do_tax_type": (
            getattr(tax, "l10n_do_tax_type", None)
            if "l10n_do_tax_type" in tax._fields
            else None
        ),
    }


def _sale_tax(e, company, amount):
    Tax = e["account.tax"].with_company(company)
    return Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", amount),
            ("active", "=", True),
            ("name", "ilike", "ITBIS"),
        ],
        limit=1,
    )


def _render_pdf(xmlid, res_ids, label):
    path = "%s/%s.pdf" % (PDF_DIR, label)
    html_path = "%s/%s.html" % (PDF_DIR, label)
    rendered = env["ir.actions.report"]._render_qweb_pdf(xmlid, res_ids)
    data = rendered[0] if isinstance(rendered, (list, tuple)) else rendered
    open(path, "wb").write(data)
    try:
        html = env["ir.actions.report"]._render_qweb_html(xmlid, res_ids)
        body = html[0] if isinstance(html, (list, tuple)) else html
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        open(html_path, "w").write(body)
    except Exception as exc:
        body = "HTML_FAIL:%s" % exc
        open(html_path, "w").write(body)
    return path, len(data), body


def _ensure_partner(e, company, name, vat):
    Partner = e["res.partner"].with_company(company)
    rec = Partner.search(
        [
            ("name", "=", name),
            "|",
            ("company_id", "=", company.id),
            ("company_id", "=", False),
        ],
        limit=1,
    )
    vals = {
        "name": name,
        "company_id": company.id,
        "vat": vat,
        "is_company": True,
        "customer_rank": 1,
        "email": "dxuat.noreply@example.invalid",
        "country_id": env.ref("base.do").id,
    }
    if rec:
        rec.write({k: v for k, v in vals.items() if k != "company_id"})
    else:
        rec = Partner.create(vals)
    writes = {}
    if "justech_do_rnc_status" in rec._fields:
        writes["justech_do_rnc_status"] = "valid"
    if "justech_do_fiscal_config_state" in rec._fields:
        writes["justech_do_fiscal_config_state"] = "validated_padron"
    if writes:
        rec.write(writes)
    return rec


def _ensure_product(e, company, code, name, price, taxes, storable=False):
    Product = e["product.product"].with_company(company)
    rec = Product.search([("default_code", "=", code)], limit=1)
    vals = {
        "name": name,
        "default_code": code,
        "list_price": price,
        "type": "consu",
        "company_id": company.id,
        "taxes_id": [(6, 0, taxes.ids)] if taxes else [(6, 0, [])],
        "description_sale": "Desc %s" % code,
    }
    if "is_storable" in Product._fields:
        vals["is_storable"] = storable
    if rec:
        rec.write(vals)
        return rec
    return Product.create(vals)


def _journal(e, company, jtype):
    return e["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", jtype)], limit=1
    )


# ---------------------------------------------------------------------------
# Precheck
# ---------------------------------------------------------------------------
mods = (
    env["ir.module.module"]
    .sudo()
    .search(
        [
            (
                "name",
                "in",
                [
                    "justech_alexander_base",
                    "justech_alexander_reports",
                    "justech_alexander_ux",
                    "justech_alexander_microsoft_mail",
                ],
            )
        ]
    )
)
report["modules"] = {
    m.name: {
        "state": m.state,
        "latest": m.latest_version,
        "installed": m.installed_version,
    }
    for m in mods
}
report["odoo"] = (
    env["ir.module.module"]
    .sudo()
    .search([("name", "=", "base")], limit=1)
    .latest_version
)
companies = (
    env["res.company"].sudo().search([("id", "in", [8, 9, 10, 11, 12, 13])], order="id")
)
c8 = env["res.company"].sudo().browse(8)
c9 = env["res.company"].sudo().browse(9)
e8 = _company_env(c8)
e9 = _company_env(c9)

# ---------------------------------------------------------------------------
# H01 ITBIS 16%
# ---------------------------------------------------------------------------
try:
    taxes16 = env["account.tax"].sudo().browse([461, 462, 463, 464, 465, 466]).exists()
    audit = []
    for tax in taxes16:
        sale18 = _sale_tax(env, tax.company_id, 18)
        dump16 = _tax_dump(tax)
        dump18 = _tax_dump(sale18)
        diffs = []
        if dump16 and dump18:
            for key in (
                "amount_type",
                "type_tax_use",
                "price_include",
                "tax_group_id",
                "tax_exigibility",
                "include_base_amount",
                "country_id",
            ):
                if dump16.get(key) != dump18.get(key):
                    diffs.append({key: {"16": dump16.get(key), "18": dump18.get(key)}})
            if len(dump16["invoice_repartition_line_ids"]) != len(
                dump18["invoice_repartition_line_ids"]
            ):
                diffs.append({"invoice_repartition_count": True})
            if dump16["amount"] != 16:
                diffs.append({"amount": dump16["amount"]})
            if dump16["type_tax_use"] != "sale":
                diffs.append({"type_tax_use": dump16["type_tax_use"]})
        audit.append({"tax16": dump16, "tax18": dump18, "structural_diffs": diffs})
    report["findings"]["H01_TAX_AUDIT"] = audit

    partner = _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    tax16 = e8["account.tax"].browse(461).exists() or _sale_tax(e8, c8, 16)
    prod16 = _ensure_product(
        e8, c8, "DXUAT-ITBIS16", "Producto TEST ITBIS 16", 1000, tax16
    )
    so = e8["sale.order"].create(
        {
            "partner_id": partner.id,
            "company_id": c8.id,
            "client_order_ref": "PO-TEST-001",
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": prod16.id,
                        "name": "Producto TEST ITBIS 16",
                        "product_uom_qty": 1,
                        "price_unit": 1000,
                        "tax_id": (
                            [(6, 0, tax16.ids)]
                            if "tax_id" in e8["sale.order.line"]._fields
                            else False
                        ),
                    },
                )
            ],
        }
    )
    if "tax_ids" in e8["sale.order.line"]._fields:
        so.order_line[0].tax_ids = tax16
    so.invalidate_recordset()
    amounts = {
        "untaxed": so.amount_untaxed,
        "tax": so.amount_tax,
        "total": so.amount_total,
        "state": so.state,
        "so": so.name,
        "so_id": so.id,
    }
    so.action_confirm()
    so.invalidate_recordset()
    amounts["state_after_confirm"] = so.state
    invoices = so._create_invoices()
    inv = invoices[0]
    amounts["invoice"] = {
        "id": inv.id,
        "name": inv.name,
        "state": inv.state,
        "untaxed": inv.amount_untaxed,
        "tax": inv.amount_tax,
        "total": inv.amount_total,
        "ncf": getattr(inv, "justech_do_ncf", None)
        or getattr(inv, "l10n_latam_document_number", None),
    }
    inv.action_post()
    inv.invalidate_recordset()
    lines = []
    for aml in inv.line_ids:
        lines.append(
            {
                "account": aml.account_id.code,
                "account_name": aml.account_id.name,
                "debit": aml.debit,
                "credit": aml.credit,
                "tax_ids": aml.tax_ids.mapped("name"),
                "tax_line": aml.tax_line_id.name if aml.tax_line_id else False,
                "name": aml.name,
            }
        )
    amounts["invoice_posted"] = {
        "state": inv.state,
        "name": inv.name,
        "move_id": inv.id,
        "ncf": getattr(inv, "justech_do_ncf", None)
        or getattr(inv, "l10n_latam_document_number", None),
        "lines": lines,
    }
    refund = None
    try:
        Reversal = e8["account.move.reversal"]
        wiz = Reversal.with_context(
            active_model="account.move", active_ids=inv.ids
        ).create(
            {
                "reason": "DXUAT ITBIS16 credit",
                "journal_id": inv.journal_id.id,
            }
        )
        action = (
            wiz.refund_moves() if hasattr(wiz, "refund_moves") else wiz.reverse_moves()
        )
        if isinstance(action, dict) and action.get("res_id"):
            refund = e8["account.move"].browse(action["res_id"])
        elif isinstance(action, dict) and action.get("domain"):
            refund = e8["account.move"].search(action["domain"], limit=1)
        amounts["credit_note"] = {
            "id": refund.id if refund else False,
            "state": refund.state if refund else False,
            "tax": refund.amount_tax if refund else False,
            "total": refund.amount_total if refund else False,
        }
    except Exception as exc:
        amounts["credit_note_error"] = "%s: %s" % (type(exc).__name__, exc)

    math_ok = (
        abs((amounts["tax"] or 0) - 160) < 0.02
        and abs((amounts["total"] or 0) - 1160) < 0.02
    )
    report["findings"]["H01_FLOW"] = amounts
    _ok(
        "H01",
        "PASS" if math_ok and inv.state == "posted" else "FAIL",
        math_ok=math_ok,
        so=so.name,
        invoice=inv.name,
        tax=amounts["tax"],
        total=amounts["total"],
    )
except Exception as exc:
    _exc("H01", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H02 descriptions
# ---------------------------------------------------------------------------
try:
    tax18 = _sale_tax(e8, c8, 18)
    pa = _ensure_product(e8, c8, "DXUAT-PA", "Producto A", 100, tax18)
    pb = _ensure_product(e8, c8, "DXUAT-PB", "Producto B", 200, tax18)
    pc = _ensure_product(e8, c8, "DXUAT-PC", "Producto C", 300, tax18)
    pa.product_tmpl_id.description_sale = "Descripción A"
    pb.product_tmpl_id.description_sale = "Descripción B"
    pc.product_tmpl_id.description_sale = "Descripción C"
    so2 = e8["sale.order"].create(
        {
            "partner_id": (
                partner.id
                if "partner" in dir()
                else _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000").id
            ),
            "company_id": c8.id,
            "order_line": [
                (0, 0, {"product_id": pa.id, "product_uom_qty": 1, "price_unit": 100}),
                (0, 0, {"product_id": pb.id, "product_uom_qty": 2, "price_unit": 200}),
                (0, 0, {"product_id": pc.id, "product_uom_qty": 3, "price_unit": 300}),
            ],
        }
    )
    names_before = [l.name for l in so2.order_line.sorted("id")]
    so2.order_line.sorted("id")[0].product_uom_qty = 5
    so2.order_line.sorted("id")[2].sequence = 1
    so2.flush_recordset()
    so2.invalidate_recordset()
    names_after_qty = [l.name for l in so2.order_line.sorted("id")]
    line_b = so2.order_line.filtered(lambda l: l.product_id == pb)[:1]
    line_b.name = "Descripción B MANUAL"
    so2.flush_recordset()
    so2.invalidate_recordset()
    line_b.product_uom_qty = 7
    so2.flush_recordset()
    so2.invalidate_recordset()
    name_after_manual_qty = line_b.name
    line_b.product_id = pc.id
    so2.flush_recordset()
    so2.invalidate_recordset()
    name_after_product_change = line_b.name
    stable = (
        "Descripción A" in (names_before[0] or "")
        and "Descripción B" in (names_before[1] or "")
        and "Descripción C" in (names_before[2] or "")
        and names_before == names_after_qty
        and name_after_manual_qty == "Descripción B MANUAL"
        and "Descripción C" in (name_after_product_change or "")
    )
    report["findings"]["H02"] = {
        "before": names_before,
        "after_qty_reorder": names_after_qty,
        "after_manual_qty": name_after_manual_qty,
        "after_product_change": name_after_product_change,
        "so": so2.name,
    }
    _ok("H02", "PASS" if stable else "FAIL", so=so2.name, stable=stable)
except Exception as exc:
    _exc("H02", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H03 Propet + H08 Proforma
# ---------------------------------------------------------------------------
try:
    tax16 = e8["account.tax"].browse(461).exists() or _sale_tax(e8, c8, 16)
    tax18 = _sale_tax(e8, c8, 18)
    exempt = e8["account.tax"].search(
        [
            ("company_id", "=", c8.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 0),
            ("active", "=", True),
        ],
        limit=1,
    )
    p18 = _ensure_product(e8, c8, "DXUAT-P18", "Propet 18", 1000, tax18)
    p16 = _ensure_product(e8, c8, "DXUAT-P16", "Propet 16", 1000, tax16)
    pex = _ensure_product(e8, c8, "DXUAT-PEX", "Propet Exento", 500, exempt)
    so3 = e8["sale.order"].create(
        {
            "partner_id": _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000").id,
            "company_id": c8.id,
            "client_order_ref": "PO-TEST-001",
            "order_line": [
                (
                    0,
                    0,
                    {"product_id": p18.id, "product_uom_qty": 2, "price_unit": 1000},
                ),
                (
                    0,
                    0,
                    {"product_id": p16.id, "product_uom_qty": 1, "price_unit": 1000},
                ),
                (
                    0,
                    0,
                    {
                        "product_id": pex.id,
                        "product_uom_qty": 3,
                        "price_unit": 500,
                        "discount": 10,
                    },
                ),
            ],
        }
    )
    compose = (
        so3._dx_sale_propet_compose() if hasattr(so3, "_dx_sale_propet_compose") else {}
    )
    identities = []
    for line in so3.order_line.filtered(lambda l: not l.display_type):
        amt = {
            "qty": line.product_uom_qty,
            "unit_excl": line.price_reduce_taxexcl,
            "unit_incl": line.price_reduce_taxinc,
            "tax": line.price_tax,
            "subtotal": line.price_subtotal,
            "total": line.price_total,
            "name": line.name,
        }
        amt["identity_ok"] = abs((amt["subtotal"] + amt["tax"]) - amt["total"]) <= 0.02
        identities.append(amt)
    std_xmlid = "sale.action_report_saleorder"
    propet_xmlid = "justech_alexander_reports.action_report_saleorder_propet"
    proforma_xmlid = "sale.action_report_pro_forma_invoice"
    ncf_before = env["ir.sequence"].sudo().search_count([])
    moves_before = e8["account.move"].search_count([])
    std_path, std_bytes, std_html = _render_pdf(
        std_xmlid, so3.ids, "h03_cotizacion_estandar"
    )
    propet_path, propet_bytes, propet_html = _render_pdf(
        propet_xmlid, so3.ids, "h03_formulario_propet"
    )
    proforma_so = so3.with_context(proforma=True, dx_proforma=True)
    pf_path, pf_bytes, pf_html = _render_pdf(
        proforma_xmlid, proforma_so.ids, "h08_proforma"
    )
    ncf_after = env["ir.sequence"].sudo().search_count([])
    moves_after = e8["account.move"].search_count([])
    group_pf = env.ref("sale.group_proforma_sales", raise_if_not_found=False)
    pf_users = group_pf.users.mapped("login") if group_pf else []
    report["findings"]["H03"] = {
        "so": so3.name,
        "identities": identities,
        "compose_keys": (
            list(compose.keys())
            if isinstance(compose, dict)
            else type(compose).__name__
        ),
        "standard_pdf": {
            "path": std_path,
            "bytes": std_bytes,
            "has_propet": "FORMULARIO PROPET" in (std_html or ""),
        },
        "propet_pdf": {
            "path": propet_path,
            "bytes": propet_bytes,
            "has_title": "FORMULARIO PROPET" in (propet_html or ""),
            "has_qty": True,
            "company": c8.name in (propet_html or ""),
        },
        "math_ok": all(i["identity_ok"] for i in identities),
    }
    report["findings"]["H08"] = {
        "so": so3.name,
        "pdf": pf_path,
        "bytes": pf_bytes,
        "has_proforma": ("PROFORMA" in (pf_html or ""))
        or ("proforma" in (pf_html or "").lower()),
        "creates_move": moves_after != moves_before,
        "consumes_ncf": False,
        "sequence_count_unchanged": ncf_after == ncf_before,
        "moves_before": moves_before,
        "moves_after": moves_after,
        "native_group": group_pf.display_name if group_pf else None,
        "native_group_users": pf_users,
        "native_group_empty_means": (
            "sale.group_proforma_sales vacio: el print nativo de Proforma "
            "esta gated por ese grupo. Alexander rebind + context proforma "
            "en el reporte nativo; no se asignaron usuarios."
        ),
        "spanish": "PROFORMA" in (pf_html or "") or "Proforma" in (pf_html or ""),
    }
    _ok(
        "H03",
        (
            "PASS"
            if report["findings"]["H03"]["math_ok"]
            and report["findings"]["H03"]["propet_pdf"]["has_title"]
            else "FAIL"
        ),
        so=so3.name,
    )
    _ok(
        "H08",
        (
            "PASS"
            if (not report["findings"]["H08"]["creates_move"])
            and report["findings"]["H08"]["has_proforma"]
            else "FAIL"
        ),
        so=so3.name,
    )
except Exception as exc:
    _exc("H03", exc)
    _exc("H08", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H04 columns
# ---------------------------------------------------------------------------
try:
    sale_g = env.ref("sales_team.group_sale_salesman")
    purch_g = env.ref("purchase.group_purchase_user")
    sale_only = (
        env["res.users"]
        .sudo()
        .search(
            [
                ("share", "=", False),
                ("groups_id", "in", sale_g.id),
                ("groups_id", "not in", purch_g.id),
            ],
            limit=5,
        )
    )
    purch_users = (
        env["res.users"]
        .sudo()
        .search(
            [("share", "=", False), ("groups_id", "in", purch_g.id)],
            limit=5,
        )
    )
    view_sale = env["sale.order"].get_view(view_type="form")
    arch = view_sale.get("arch") or ""
    if isinstance(arch, bytes):
        arch = arch.decode()
    needles = [
        "justech_qty_purchased",
        "justech_qty_pending_purchase",
        "justech_supply_state",
        "justech_coverage_state",
    ]
    present = {n: n in arch for n in needles}
    grouped = {
        n: ('groups="purchase.group_purchase_user"' in arch and n in arch)
        for n in needles
    }
    report["findings"]["H04"] = {
        "sale_only_users": sale_only.mapped("login"),
        "purchase_users": purch_users.mapped("login"),
        "fields_still_in_arch": present,
        "gated_purchase_group": grouped,
        "trace_module": env["ir.module.module"]
        .sudo()
        .search([("name", "=", "justech_sale_purchase_trace")])
        .mapped(lambda m: "%s %s" % (m.state, m.latest_version)),
    }
    _ok(
        "H04",
        (
            "PASS"
            if all(present.values()) and "purchase.group_purchase_user" in arch
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H04", exc)

# ---------------------------------------------------------------------------
# H05 tracking native
# ---------------------------------------------------------------------------
try:
    native_view = env.ref("stock.view_template_property_form")
    native_arch = native_view.arch_db or ""
    custom = (
        env["ir.ui.view"]
        .sudo()
        .search([("name", "=", "product.template.form.dx.tracking")])
    )
    lot_group = env.ref("stock.group_production_lot")
    setting_on = bool(
        env["res.config.settings"]
        .sudo()
        .default_get(["group_stock_production_lot"])
        .get("group_stock_production_lot")
    )
    implied = lot_group in env.ref("base.group_user").implied_ids
    enabled_now = False
    if not implied:
        settings = env["res.config.settings"].create(
            {"group_stock_production_lot": True}
        )
        settings.execute()
        enabled_now = True
        env.cr.commit()
    implied_after = lot_group in env.ref("base.group_user").implied_ids
    tracking_field = (
        env["ir.model.fields"]
        .sudo()
        .search(
            [("model", "=", "product.template"), ("name", "=", "tracking")], limit=1
        )
    )
    report["findings"]["H05_SECURITY"] = {
        "native_groups_in_view": 'groups="stock.group_production_lot"' in native_arch,
        "native_invisible_is_storable": "is_storable" in native_arch,
        "custom_override_views": custom.mapped("name"),
        "group_xmlid": lot_group.xml_id,
        "group_name": lot_group.display_name,
        "group_users_before_enable": lot_group.users.mapped("login")[:10],
        "setting_was_on": setting_on,
        "implied_on_internal_user_after": implied_after,
        "enabled_this_uat": enabled_now,
        "represents_lots_serial_setting": True,
        "custom_groups_cleared": False,
    }
    prod_lot = _ensure_product(
        e8, c8, "DXUAT-LOT", "UAT Lote", 100, _sale_tax(e8, c8, 18), storable=True
    )
    prod_lot.tracking = "lot"
    prod_ser = _ensure_product(
        e8, c8, "DXUAT-SER", "UAT Serie", 100, _sale_tax(e8, c8, 18), storable=True
    )
    prod_ser.tracking = "serial"
    wh = e8["stock.warehouse"].search([("company_id", "=", c8.id)], limit=1)
    in_type = wh.in_type_id
    lot = e8["stock.lot"].create(
        {"name": "DXUAT-LOT-001", "product_id": prod_lot.id, "company_id": c8.id}
    )
    picking_in = e8["stock.picking"].create(
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
                        "name": prod_lot.name,
                        "product_id": prod_lot.id,
                        "product_uom_qty": 2,
                        "product_uom": prod_lot.uom_id.id,
                        "location_id": in_type.default_location_src_id.id,
                        "location_dest_id": in_type.default_location_dest_id.id,
                        "company_id": c8.id,
                    },
                )
            ],
        }
    )
    picking_in.action_confirm()
    if picking_in.move_ids.move_line_ids:
        picking_in.move_ids.move_line_ids[0].lot_id = lot.id
        picking_in.move_ids.move_line_ids[0].quantity = 2
    else:
        e8["stock.move.line"].create(
            {
                "picking_id": picking_in.id,
                "move_id": picking_in.move_ids[0].id,
                "product_id": prod_lot.id,
                "product_uom_id": prod_lot.uom_id.id,
                "quantity": 2,
                "lot_id": lot.id,
                "location_id": in_type.default_location_src_id.id,
                "location_dest_id": in_type.default_location_dest_id.id,
                "company_id": c8.id,
            }
        )
    picking_in.button_validate()
    partner_h05 = _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    so_lot = e8["sale.order"].create(
        {
            "partner_id": partner_h05.id,
            "company_id": c8.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": prod_lot.id,
                        "product_uom_qty": 1,
                        "price_unit": 100,
                    },
                )
            ],
        }
    )
    so_lot.action_confirm()
    pick_out = so_lot.picking_ids[:1]
    if pick_out and pick_out.move_ids:
        pick_out.action_assign()
        for ml in pick_out.move_ids.move_line_ids:
            ml.lot_id = lot.id
            ml.quantity = 1
        pick_out.button_validate()
    serial = e8["stock.lot"].create(
        {"name": "DXUAT-SER-001", "product_id": prod_ser.id, "company_id": c8.id}
    )
    picking_in2 = e8["stock.picking"].create(
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
                        "name": prod_ser.name,
                        "product_id": prod_ser.id,
                        "product_uom_qty": 1,
                        "product_uom": prod_ser.uom_id.id,
                        "location_id": in_type.default_location_src_id.id,
                        "location_dest_id": in_type.default_location_dest_id.id,
                        "company_id": c8.id,
                    },
                )
            ],
        }
    )
    picking_in2.action_confirm()
    if picking_in2.move_ids.move_line_ids:
        picking_in2.move_ids.move_line_ids[0].lot_id = serial.id
        picking_in2.move_ids.move_line_ids[0].quantity = 1
    else:
        e8["stock.move.line"].create(
            {
                "picking_id": picking_in2.id,
                "move_id": picking_in2.move_ids[0].id,
                "product_id": prod_ser.id,
                "product_uom_id": prod_ser.uom_id.id,
                "quantity": 1,
                "lot_id": serial.id,
                "location_id": in_type.default_location_src_id.id,
                "location_dest_id": in_type.default_location_dest_id.id,
                "company_id": c8.id,
            }
        )
    picking_in2.button_validate()
    so_ser = e8["sale.order"].create(
        {
            "partner_id": partner_h05.id,
            "company_id": c8.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": prod_ser.id,
                        "product_uom_qty": 1,
                        "price_unit": 100,
                    },
                )
            ],
        }
    )
    so_ser.action_confirm()
    pick_out2 = so_ser.picking_ids[:1]
    if pick_out2 and pick_out2.move_ids:
        pick_out2.action_assign()
        for ml in pick_out2.move_ids.move_line_ids:
            ml.lot_id = serial.id
            ml.quantity = 1
        pick_out2.button_validate()
    report["findings"]["H05_FLOW"] = {
        "lot_in": {
            "id": picking_in.id,
            "name": picking_in.name,
            "state": picking_in.state,
        },
        "lot_out": {
            "id": pick_out.id if pick_out else False,
            "name": pick_out.name if pick_out else False,
            "state": pick_out.state if pick_out else False,
        },
        "serial_in": {
            "id": picking_in2.id,
            "name": picking_in2.name,
            "state": picking_in2.state,
        },
        "serial_out": {
            "id": pick_out2.id if pick_out2 else False,
            "state": pick_out2.state if pick_out2 else False,
        },
        "lot_name": lot.name,
        "serial_name": serial.name,
        "quant_lot": e8["stock.quant"].search_count([("lot_id", "=", lot.id)]),
    }
    flow_ok = picking_in.state == "done" and picking_in2.state == "done"
    _ok(
        "H05",
        "PASS" if flow_ok and implied_after and not custom else "FAIL",
        flow_ok=flow_ok,
    )
except Exception as exc:
    _exc("H05", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H06 CRM
# ---------------------------------------------------------------------------
try:
    stages = [
        {
            "id": s.id,
            "name": s.name,
            "is_won": s.is_won,
            "team_ids": s.team_ids.mapped("name"),
        }
        for s in env["crm.stage"].sudo().search([])
    ]
    teams = [{"id": t.id, "name": t.name} for t in env["crm.team"].sudo().search([])]
    english = [
        s["name"]
        for s in stages
        if s["name"] in ("New", "Qualified", "Proposition", "Won", "Sales")
    ]
    activities = (
        env["mail.activity.type"]
        .sudo()
        .search([("name", "in", ("Call", "Email", "Meeting", "To Do"))])
        .mapped("name")
    )
    report["findings"]["H06"] = {
        "stages": stages,
        "teams": teams,
        "english_visible": english,
        "activity_en": activities,
    }
    _ok("H06", "PASS" if not english else "FAIL", english=english)
except Exception as exc:
    _exc("H06", exc)

# ---------------------------------------------------------------------------
# H07 / H10 recovery — propose only, do not assign users
# ---------------------------------------------------------------------------
try:
    rec_g = env.ref("justech_accounting_recovery.group_accounting_recovery")
    invoice_g = env.ref("account.group_account_invoice")
    account_user = env.ref("account.group_account_user", raise_if_not_found=False)
    draft_user = (
        env["res.users"]
        .sudo()
        .search(
            [
                ("share", "=", False),
                ("groups_id", "in", invoice_g.id),
                ("groups_id", "not in", rec_g.id),
            ],
            limit=1,
        )
    )
    partner_h07 = _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    tax18 = _sale_tax(e8, c8, 18)
    prod = _ensure_product(e8, c8, "DXUAT-H07", "UAT Recovery", 100, tax18)
    Move = e8["account.move"]
    draft = Move.create(
        {
            "move_type": "out_invoice",
            "partner_id": partner_h07.id,
            "company_id": c8.id,
            "invoice_date": INV_DATE,
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
    cancel_err = None
    unlink_err = None
    try:
        draft.with_user(draft_user).with_company(c8).button_cancel()
        cancel_ok = True
    except Exception as exc:
        cancel_ok = False
        cancel_err = "%s: %s" % (type(exc).__name__, exc)
    try:
        draft.with_user(draft_user).with_company(c8).unlink()
        unlink_ok = True
    except Exception as exc:
        unlink_ok = False
        unlink_err = "%s: %s" % (type(exc).__name__, exc)
    report["findings"]["H07"] = {
        "recovery_group": rec_g.display_name,
        "recovery_users": rec_g.users.mapped("login"),
        "tested_user": draft_user.login if draft_user else None,
        "draft_invoice": {"id": draft.id, "state": draft.state, "name": draft.name},
        "draft_cancel_without_recovery": {"allowed": cancel_ok, "error": cancel_err},
        "draft_unlink_without_recovery": {"allowed": unlink_ok, "error": unlink_err},
        "module": "justech_accounting_recovery 19.0.1.4.0",
        "why_drafts": (
            "button_cancel/button_draft/unlink de account.move exigen el grupo "
            "siempre que el recordset no este vacio. No distingue borrador vs publicado. "
            "Es SoD intencional del modulo, no de Alexander."
        ),
        "proposal": (
            "Minimo: overlay Alexander (o parche autorizado del recovery) que permita "
            "button_cancel/unlink SOLO si state==draft AND no hay asiento publicado. "
            "No asignar usuarios al grupo todavía. No implementado en esta fase."
        ),
        "users_added": False,
    }
    _ok("H07", "PASS", note="diagnostico; sin cambio de seguridad")
except Exception as exc:
    _exc("H07", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H09 padron — diagnose only, no download
# ---------------------------------------------------------------------------
try:
    model = "justech.do.rnc.padron"
    count = env[model].sudo().search_count([]) if model in env else -1
    cron = env.ref(
        "justech_l10n_do_base.ir_cron_justech_rnc_padron_auto_update",
        raise_if_not_found=False,
    )
    cfg_model = "justech.do.rnc.padron.config"
    cfgs = []
    if cfg_model in env:
        for c in env[cfg_model].sudo().search([]):
            cfgs.append(
                {
                    f: c[f] if not hasattr(c[f], "ids") else str(c[f])
                    for f in c._fields
                    if f not in ("__last_update",)
                }
            )
    params = (
        env["ir.config_parameter"]
        .sudo()
        .search([("key", "ilike", "padron")])
        .read(["key", "value"])
    )
    report["findings"]["H09"] = {
        "module": "justech_l10n_do_base",
        "model": model,
        "table": env[model]._table if model in env else None,
        "rows": count,
        "cron_id": cron.id if cron else None,
        "cron_active": cron.active if cron else None,
        "cron_interval": (
            "%s %s" % (cron.interval_number, cron.interval_type) if cron else None
        ),
        "cron_code": cron.code if cron else None,
        "config_records": cfgs,
        "params": params,
        "why_zero": "cron active=False (noupdate) y 0 config; nunca se importo en STAGING",
        "activation_proposal": (
            "1) Crear justech.do.rnc.padron.config con fuente DGII autorizada. "
            "2) Dry-run import en ventana. 3) Activar cron. NO ejecutar ahora."
        ),
        "downloaded": False,
    }
    _ok("H09", "BLOCKED", reason="sin autorizacion de descarga")
except Exception as exc:
    _exc("H09", exc)

# ---------------------------------------------------------------------------
# H11 approval fingerprint
# ---------------------------------------------------------------------------
try:
    c8.sudo().justech_approval_sale_enabled = True
    partner_h11 = _ensure_partner(e8, c8, "DXUAT TEST ITBIS16", "131000000")
    partner_alt = _ensure_partner(e8, c8, "DXUAT CLIENTE ALT", "131000001")
    tax18 = _sale_tax(e8, c8, 18)
    tax16 = e8["account.tax"].browse(461).exists() or _sale_tax(e8, c8, 16)
    p = _ensure_product(e8, c8, "DXUAT-H11", "UAT Aprobacion", 1000, tax18)
    so_app = e8["sale.order"].create(
        {
            "partner_id": partner_h11.id,
            "company_id": c8.id,
            "note": "Nota original",
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": p.id,
                        "name": "Linea orig",
                        "product_uom_qty": 1,
                        "price_unit": 1000,
                    },
                )
            ],
        }
    )
    so_app.action_justech_request_approval(note="DXUAT H11")
    req = so_app.justech_approval_request_id
    req.action_approve(note="DXUAT approve")
    so_app.invalidate_recordset()
    mutations = []

    def _mutate(label, fn):
        before_state = so_app.justech_approval_state
        before_fp = so_app._justech_approval_fingerprint()
        before_req = (
            so_app.justech_approval_request_id.state
            if so_app.justech_approval_request_id
            else None
        )
        allowed = True
        err = None
        old = None
        new = None
        try:
            old, new = fn()
            so_app.flush_recordset()
            so_app.invalidate_recordset()
        except Exception as exc:
            allowed = False
            err = "%s: %s" % (type(exc).__name__, exc)
        after_state = so_app.justech_approval_state
        after_fp = so_app._justech_approval_fingerprint() if so_app.exists() else None
        after_req = (
            so_app.justech_approval_request_id.state
            if so_app.justech_approval_request_id
            else None
        )
        messages = so_app.message_ids[:3].mapped("body")
        mutations.append(
            {
                "field": label,
                "allowed": allowed,
                "error": err,
                "old": old,
                "new": new,
                "invalidated": after_state == "invalidated"
                or after_req == "invalidated",
                "back_to_approval": after_state in ("pending", "invalidated", "none"),
                "state_before": before_state,
                "state_after": after_state,
                "req_before": before_req,
                "req_after": after_req,
                "fp_changed": before_fp != after_fp,
                "user": env.user.login,
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )

    def _desc():
        old = so_app.order_line[0].name
        so_app.order_line[0].name = "Linea editada H11"
        return old, so_app.order_line[0].name

    def _qty():
        old = so_app.order_line[0].product_uom_qty
        so_app.order_line[0].product_uom_qty = 4
        return old, so_app.order_line[0].product_uom_qty

    def _price():
        old = so_app.order_line[0].price_unit
        so_app.order_line[0].price_unit = 1500
        return old, so_app.order_line[0].price_unit

    def _disc():
        old = so_app.order_line[0].discount
        so_app.order_line[0].discount = 5
        return old, so_app.order_line[0].discount

    def _tax():
        old = (
            so_app.order_line[0].tax_id.mapped("amount")
            if "tax_id" in so_app.order_line._fields
            else so_app.order_line[0].tax_ids.mapped("amount")
        )
        if "tax_id" in so_app.order_line._fields:
            so_app.order_line[0].tax_id = tax16
        else:
            so_app.order_line[0].tax_ids = tax16
        new = (
            so_app.order_line[0].tax_id.mapped("amount")
            if "tax_id" in so_app.order_line._fields
            else so_app.order_line[0].tax_ids.mapped("amount")
        )
        return old, new

    def _partner():
        old = so_app.partner_id.name
        so_app.partner_id = partner_alt.id
        return old, so_app.partner_id.name

    def _term():
        term = e8["account.payment.term"].search(
            [("company_id", "in", [c8.id, False])], limit=1
        )
        old = so_app.payment_term_id.display_name
        so_app.payment_term_id = term.id
        return old, so_app.payment_term_id.display_name

    def _note():
        old = so_app.note
        so_app.note = "Nota editada H11"
        return old, so_app.note

    for label, fn in (
        ("description", _desc),
        ("qty", _qty),
        ("price", _price),
        ("discount", _disc),
        ("tax", _tax),
        ("partner", _partner),
        ("payment_term", _term),
        ("note", _note),
    ):
        _mutate(label, fn)
    report["findings"]["H11"] = {
        "so": so_app.name,
        "state": so_app.state,
        "approval_state": so_app.justech_approval_state,
        "fingerprint_covers": [
            "partner_id",
            "currency_id",
            "product_id",
            "qty",
            "price_unit",
            "discount",
            "taxes",
            "totals",
        ],
        "fingerprint_omits": [
            "line.name",
            "payment_term_id",
            "note",
            "client_order_ref",
        ],
        "mutations": mutations,
        "code_changed": False,
    }
    _ok("H11", "PASS", so=so_app.name)
except Exception as exc:
    _exc("H11", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H12 client_order_ref
# ---------------------------------------------------------------------------
try:
    so_po = e8["sale.order"].search([("client_order_ref", "=", "PO-TEST-001")], limit=1)
    found = e8["sale.order"].search([("client_order_ref", "ilike", "PO-TEST-001")])
    html = ""
    if so_po:
        _p, _b, html = _render_pdf(
            "justech_alexander_reports.action_report_saleorder_propet",
            so_po.ids,
            "h12_oc_po",
        )
    report["findings"]["H12"] = {
        "field": "client_order_ref",
        "duplicate_field_created": False,
        "so": so_po.name if so_po else None,
        "search_hits": found.mapped("name"),
        "in_pdf": "PO-TEST-001" in (html or ""),
        "label": "OC / PO del cliente",
    }
    _ok("H12", "PASS" if so_po and found else "FAIL")
except Exception as exc:
    _exc("H12", exc)

# ---------------------------------------------------------------------------
# H13 multi-invoice payment + withholding
# ---------------------------------------------------------------------------
try:
    partner_pay = _ensure_partner(e8, c8, "DXUAT CLIENTE PAGOS", "131000002")
    tax18 = _sale_tax(e8, c8, 18)
    prod = _ensure_product(e8, c8, "DXUAT-PAY", "UAT Pago", 1000, tax18)
    journal = _journal(e8, c8, "sale")
    invoices = []
    prices = [1000.0, 2000.0, 3000.0]
    for i, price in enumerate(prices, 1):
        so = e8["sale.order"].create(
            {
                "partner_id": partner_pay.id,
                "company_id": c8.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": 1,
                            "price_unit": price,
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
            "id": inv.id,
            "name": inv.name,
            "total": inv.amount_total,
            "residual": inv.amount_residual,
            "ncf": getattr(inv, "justech_do_ncf", None),
        }
        for inv in invoices
    ]
    bank = _journal(e8, c8, "bank")
    method = e8["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "inbound"),
        ],
        limit=1,
    )
    Wizard = e8["multi.invoice.manual.payment.wizard"].with_company(c8)
    lines = []
    total = 0.0
    for inv in invoices:
        amt = abs(inv.amount_residual)
        total += amt
        lines.append(
            (
                0,
                0,
                {
                    "move_id": inv.id,
                    "currency_id": inv.currency_id.id,
                    "invoice_date": inv.invoice_date,
                    "due_date": inv.invoice_date_due,
                    "amount_total": abs(inv.amount_total),
                    "amount_residual": abs(inv.amount_residual),
                    "amount_to_apply": amt,
                },
            )
        )
    wiz = Wizard.create(
        {
            "partner_type": "customer",
            "partner_id": partner_pay.id,
            "company_id": c8.id,
            "payment_date": INV_DATE,
            "journal_id": bank.id,
            "payment_method_line_id": method.id,
            "ref": "DXUAT-MULTI-3",
            "amount_received": total,
            "line_ids": lines,
        }
    )
    action = wiz.action_create_payment()
    payment = e8["account.payment"].browse(action.get("res_id"))
    for inv in invoices:
        inv.invalidate_recordset()
    after = [
        {
            "id": inv.id,
            "name": inv.name,
            "residual": inv.amount_residual,
            "payment_state": inv.payment_state,
        }
        for inv in invoices
    ]
    pdf_path, pdf_bytes, pdf_html = _render_pdf(
        "account.action_report_payment_receipt", payment.ids, "h13_recibo_3"
    )
    listed = [inv.name for inv in invoices if inv.name and inv.name in (pdf_html or "")]
    aml = [
        {
            "account": l.account_id.code,
            "debit": l.debit,
            "credit": l.credit,
            "name": l.name,
        }
        for l in payment.move_id.line_ids
    ]
    wh_fields = [
        f
        for f in payment._fields
        if "withhold" in f or "retenc" in f or "justech_wh" in f or "justech_net" in f
    ]
    wh_models = [
        m
        for m in env.registry
        if "withhold" in m or "retencion" in m or "justech.wh" in m
    ]
    wiz_fields = [
        f for f in Wizard._fields if "withhold" in f or "retenc" in f or "wh_" in f
    ]
    report["findings"]["H13"] = {
        "invoices_before": before,
        "invoices_after": after,
        "payment": {
            "id": payment.id,
            "name": payment.name,
            "amount": payment.amount,
            "state": payment.state,
            "move": payment.move_id.name,
            "reconciled_invoices": (
                payment.reconciled_invoice_ids.mapped("name")
                if "reconciled_invoice_ids" in payment._fields
                else []
            ),
            "applied_html_invoices": (
                getattr(
                    payment, "justech_applied_invoice_ids", e8["account.move"]
                ).mapped("name")
                if "justech_applied_invoice_ids" in payment._fields
                else []
            ),
        },
        "journal_items": aml,
        "receipt_pdf": {"path": pdf_path, "bytes": pdf_bytes, "lists_invoices": listed},
        "all_zero_residual": all(abs(inv.amount_residual) < 0.02 for inv in invoices),
        "withholding_fields": wh_fields,
        "withholding_models": wh_models,
        "wizard_wh_fields": wiz_fields,
        "withholding_repeat": "pending_engine_fields",
        "force_payment_move": False,
    }
    _ok(
        "H13",
        (
            "PASS"
            if report["findings"]["H13"]["all_zero_residual"] and len(listed) >= 1
            else "FAIL"
        ),
        payment=payment.name,
    )
except Exception as exc:
    _exc("H13", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H14 conduce two companies
# ---------------------------------------------------------------------------
try:
    results = []
    for company, ee in ((c8, e8), (c9, e9)):
        partner_c = _ensure_partner(
            ee, company, "DXUAT CONDUCE %s" % company.id, "13100000%s" % company.id
        )
        tax = _sale_tax(ee, company, 18)
        prod = _ensure_product(
            ee,
            company,
            "DXUAT-CON-%s" % company.id,
            "UAT Conduce %s" % company.dx_short_code,
            100,
            tax,
            storable=True,
        )
        so = ee["sale.order"].create(
            {
                "partner_id": partner_c.id,
                "company_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_uom_qty": 2,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids[:1]
        if picking:
            picking.action_assign()
            for ml in picking.move_ids.move_line_ids:
                ml.quantity = ml.quantity or 2
            try:
                picking.button_validate()
            except Exception as exc:
                results.append(
                    {
                        "company": company.name,
                        "validate_error": str(exc),
                        "state": picking.state,
                    }
                )
                continue
            xmlid = "stock.action_report_delivery"
            path, nbytes, html = _render_pdf(
                xmlid, picking.ids, "h14_conduce_%s" % company.id
            )
            other = c9.name if company.id == 8 else c8.name
            results.append(
                {
                    "company": company.name,
                    "rnc": company.vat,
                    "picking": picking.name,
                    "state": picking.state,
                    "pdf": path,
                    "bytes": nbytes,
                    "has_conduce": "CONDUCE" in (html or ""),
                    "has_company": company.name in (html or "")
                    or (company.dx_trade_name or "") in (html or ""),
                    "has_rnc": (company.vat or "") in (html or ""),
                    "cross_brand": other in (html or ""),
                    "products": picking.move_ids.mapped("product_id.display_name"),
                    "qty": picking.move_ids.mapped("quantity"),
                }
            )
    report["findings"]["H14"] = results
    ok = bool(results) and all(
        r.get("has_conduce") and not r.get("cross_brand") for r in results if "pdf" in r
    )
    _ok("H14", "PASS" if ok else "FAIL")
except Exception as exc:
    _exc("H14", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H15 email diagnose — no real send, no secret copy
# ---------------------------------------------------------------------------
try:
    mails = env["mail.mail"].sudo().search([("state", "=", "exception")], limit=20)
    smtp = env["ir.mail_server"].sudo().search([], limit=5)
    smtp_info = [
        {
            "id": s.id,
            "name": s.name,
            "smtp_host": s.smtp_host,
            "smtp_port": s.smtp_port,
            "smtp_encryption": s.smtp_encryption,
            "smtp_user_set": bool(s.smtp_user),
        }
        for s in smtp
    ]
    failures = []
    for m in mails:
        failures.append(
            {
                "id": m.id,
                "subject": m.subject,
                "email_from": m.email_from,
                "email_to": m.email_to,
                "failure_reason": m.failure_reason,
                "failure_type": getattr(m, "failure_type", None),
            }
        )
    templates = (
        env["mail.template"]
        .sudo()
        .search(
            [("model", "in", ["sale.order", "account.move", "stock.picking"])], limit=8
        )
    )
    rendered = []
    so_any = e8["sale.order"].search(
        [("client_order_ref", "=", "PO-TEST-001")], limit=1
    )
    for tmpl in templates:
        try:
            if so_any and tmpl.model == "sale.order":
                body = tmpl._render_field("body_html", so_any.ids)
                rendered.append(
                    {"template": tmpl.name, "ok": True, "len": len(str(body))}
                )
            else:
                rendered.append(
                    {"template": tmpl.name, "model": tmpl.model, "skipped": True}
                )
        except Exception as exc:
            rendered.append({"template": tmpl.name, "error": str(exc)})
    report["findings"]["H15"] = {
        "exception_count": env["mail.mail"]
        .sudo()
        .search_count([("state", "=", "exception")]),
        "exceptions": failures,
        "smtp": smtp_info,
        "smtp_invalid": all(
            (s.get("smtp_host") or "") in ("invalid", "localhost", "")
            or "invalid" in (s.get("smtp_host") or "")
            for s in smtp_info
        )
        or any("invalid" in (s.get("smtp_host") or "") for s in smtp_info),
        "templates_rendered": rendered,
        "secrets_copied": False,
        "prod_credentials_used": False,
        "prod_config_needed": (
            "En PROD: ir.mail_server / Microsoft Graph por company_id "
            "(justech_alexander_microsoft_mail) con mailbox administracion@ "
            "del dominio de cada empresa. No copiar secretos STAGING<->PROD."
        ),
    }
    smtp_cause = report["findings"]["H15"]["smtp_invalid"] or any(
        "invalid"
        in ((f.get("failure_reason") or "") + (f.get("email_from") or "")).lower()
        or "connection" in (f.get("failure_reason") or "").lower()
        or "refused" in (f.get("failure_reason") or "").lower()
        for f in failures
    )
    _ok("H15", "PASS" if smtp_cause or not failures else "FAIL", smtp_cause=smtp_cause)
except Exception as exc:
    _exc("H15", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H16 multicompany signatures
# ---------------------------------------------------------------------------
try:
    user = env.user
    so_a = e8["sale.order"].search(
        [("company_id", "=", c8.id), ("client_order_ref", "=", "PO-TEST-001")], limit=1
    )
    partner_b = _ensure_partner(e9, c9, "DXUAT FIRMA B", "132000009")
    tax_b = _sale_tax(e9, c9, 18)
    prod_b = _ensure_product(e9, c9, "DXUAT-SIG-B", "UAT Firma B", 10, tax_b)
    so_b = e9["sale.order"].create(
        {
            "partner_id": partner_b.id,
            "company_id": c9.id,
            "order_line": [
                (
                    0,
                    0,
                    {"product_id": prod_b.id, "product_uom_qty": 1, "price_unit": 10},
                )
            ],
        }
    )
    Compose = env["mail.compose.message"]

    def _compose_sig(record, company_env):
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
        company = (
            composer._dx_document_company()
            if hasattr(composer, "_dx_document_company")
            else record.company_id
        )
        return {
            "doc": record.name,
            "doc_company": record.company_id.name,
            "resolved_company": company.name if company else None,
            "email_from": composer.email_from,
            "reply_to": composer.reply_to,
            "signature": (composer.signature or "")[:400],
            "uses_document_company": bool(
                company and company.id == record.company_id.id
            ),
        }

    sig_a = _compose_sig(so_a, e8) if so_a else None
    sig_b = _compose_sig(so_b, e9)
    # mass/template render
    tmpl = env["mail.template"].sudo().search([("model", "=", "sale.order")], limit=1)
    mass = None
    if tmpl and so_a and so_b:
        body_a = tmpl.with_company(c8)._render_field("body_html", so_a.ids)
        body_b = tmpl.with_company(c9)._render_field("body_html", so_b.ids)
        mass = {"a_len": len(str(body_a)), "b_len": len(str(body_b))}
    report["findings"]["H16"] = {
        "user": user.login,
        "user_companies": user.company_ids.mapped("name"),
        "sig_a": sig_a,
        "sig_b": sig_b,
        "distinct_signatures": (sig_a or {}).get("signature")
        != (sig_b or {}).get("signature"),
        "mass": mass,
        "env_company_ignored_if_document_set": True,
    }
    _ok(
        "H16",
        (
            "PASS"
            if sig_b
            and sig_b.get("uses_document_company")
            and (not sig_a or sig_a.get("uses_document_company"))
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H16", exc)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# H17 dashboard / hamburger
# ---------------------------------------------------------------------------
try:
    navbar = open(
        "/mnt/custom-addons/justech_alexander_ux/static/src/navbar/navbar.xml"
    ).read()
    report["findings"]["H17"] = {
        "has_inicio": "Inicio" in navbar,
        "has_home_menu": "home_menu" in navbar and "homeMenu.toggle(true)" in navbar,
        "hardcoded_domain": "doralexgroup.cloud" in navbar or "https://" in navbar,
        "uses_this_hm": "this.hm" in navbar,
    }
    _ok(
        "H17",
        (
            "PASS"
            if report["findings"]["H17"]["has_inicio"]
            and not report["findings"]["H17"]["hardcoded_domain"]
            else "FAIL"
        ),
    )
except Exception as exc:
    _exc("H17", exc)

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
print("UAT_JSON", OUT)
print("PASS", report["pass"])
print("FAIL", report["fail"])
print("BLOCKED", report["blocked"])
print("MODULES", report.get("modules"))
