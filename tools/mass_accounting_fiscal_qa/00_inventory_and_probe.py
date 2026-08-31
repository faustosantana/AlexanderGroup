# -*- coding: utf-8 -*-
"""Staging-only inventory + one-invoice probe. Prefix DXQA. No mail. No prod."""

import json
from collections import defaultdict

OUT = "/tmp/mass_qa_inventory.json"
ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

data = {
    "qweb_alexander": env["ir.ui.view"].search_count(
        [("key", "like", "justech_alexander%")]
    ),
    "ecf_params": [],
    "modules": [],
    "companies": [],
    "ncf_types": [],
    "ncf_ranges": [],
    "withholding_configs": [],
    "dgii_models": [],
    "reversal_fields": [],
    "probe": {},
}

for p in env["ir.config_parameter"].sudo().search([("key", "ilike", "ecf")]):
    data["ecf_params"].append({"key": p.key, "value": p.value})

for name in (
    "justech_l10n_do_ncf",
    "justech_l10n_do_reports",
    "justech_l10n_do_payments_withholding",
    "multi_invoice_manual_payment_prod",
    "justech_purchase_sale_margin_control",
    "justech_sale_purchase_trace",
    "justech_alexander_reports",
    "justech_global_audit_log",
    "justech_approval_flow",
):
    mod = env["ir.module.module"].search([("name", "=", name)], limit=1)
    data["modules"].append(
        {
            "name": name,
            "state": mod.state if mod else "missing",
            "version": mod.latest_version if mod else None,
        }
    )

if "justech.do.fiscal.document.type" in env:
    for t in env["justech.do.fiscal.document.type"].search([]):
        data["ncf_types"].append(
            {
                "id": t.id,
                "prefix": t.prefix,
                "name": t.name,
                "company_id": t.company_id.id if t.company_id else None,
            }
        )

if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].search([]):
        journals = []
        if "journal_ids" in r._fields:
            journals = [j.display_name for j in r.journal_ids]
        data["ncf_ranges"].append(
            {
                "id": r.id,
                "company_id": r.company_id.id,
                "company": r.company_id.name,
                "prefix": r.prefix or r.document_type_id.prefix,
                "type": r.document_type_id.name if r.document_type_id else None,
                "start": r.sequence_start,
                "end": r.sequence_end,
                "next": r.next_sequence,
                "remaining": (
                    (r.sequence_end - r.next_sequence + 1) if r.next_sequence else None
                ),
                "state": r.state,
                "date_from": str(r.date_from or ""),
                "date_to": str(r.date_to or ""),
                "journals": journals,
            }
        )

if "justech.do.withholding.company.config" in env:
    for w in env["justech.do.withholding.company.config"].search([]):
        data["withholding_configs"].append(
            {
                "id": w.id,
                "company_id": w.company_id.id,
                "code": w.catalog_code,
                "name": w.catalog_name,
                "rate": w.rate,
                "active_config": w.active_config,
                "state": w.state,
                "move_scope": w.move_scope,
            }
        )

for model_name in (
    "justech.do.fiscal.report",
    "justech.do.fiscal.report.wizard",
    "justech.do.dgii.606.exporter",
    "justech.do.dgii.607.exporter",
    "justech.do.dgii.608.exporter",
    "justech.do.dgii.609.exporter",
    "justech.do.dgii.623.exporter",
    "account.move.reversal",
    "multi.invoice.manual.payment.wizard",
    "justech.do.ncf.void.wizard",
):
    data["dgii_models"].append({"model": model_name, "present": model_name in env})

if "account.move.reversal" in env:
    data["reversal_fields"] = sorted(env["account.move.reversal"]._fields.keys())
    data["reversal_methods"] = [
        m
        for m in ("refund_moves", "modify_moves", "reverse_moves")
        if hasattr(env["account.move.reversal"], m)
    ]

for company in env["res.company"].search([("active", "=", True)], order="id"):
    env_c = env(context=dict(env.context, allowed_company_ids=[company.id], **ctx_mail))
    journals = env_c["account.journal"].search(
        [("company_id", "=", company.id), ("active", "=", True)]
    )
    by_type = defaultdict(list)
    for j in journals:
        by_type[j.type].append({"id": j.id, "name": j.name, "code": j.code})
    sale_taxes = env_c["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "sale"),
            ("active", "=", True),
        ]
    )
    purch_taxes = env_c["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "purchase"),
            ("active", "=", True),
        ]
    )
    bank = journals.filtered(lambda j: j.type == "bank")[:1]
    inbound = outbound = None
    if bank:
        pml = env_c["account.payment.method.line"].search(
            [("journal_id", "=", bank.id)]
        )
        for line in pml:
            ptype = line.payment_method_id.payment_type
            if ptype == "inbound" and not inbound:
                inbound = {"id": line.id, "name": line.name}
            if ptype == "outbound" and not outbound:
                outbound = {"id": line.id, "name": line.name}
    fiscal_country = (
        company.account_fiscal_country_id.code
        if company.account_fiscal_country_id
        else None
    )
    data["companies"].append(
        {
            "id": company.id,
            "name": company.name,
            "rnc": company.partner_id.vat or "",
            "currency": company.currency_id.name,
            "fiscal_country": fiscal_country,
            "justech_do_fiscal_enabled": bool(
                getattr(company, "justech_do_fiscal_enabled", False)
            ),
            "vendor_bill_po_policy": getattr(
                company, "justech_vendor_bill_po_policy", None
            ),
            "approval_invoice": getattr(
                company, "justech_approval_invoice_enabled", None
            ),
            "journals": dict(by_type),
            "sale_taxes": [
                {"id": t.id, "name": t.name, "amount": t.amount} for t in sale_taxes
            ],
            "purchase_taxes": [
                {"id": t.id, "name": t.name, "amount": t.amount} for t in purch_taxes
            ],
            "inbound_method": inbound,
            "outbound_method": outbound,
            "ncf_configured": any(
                r["company_id"] == company.id for r in data["ncf_ranges"]
            ),
            "accounting_configured": bool(
                by_type.get("sale") and by_type.get("purchase")
            ),
        }
    )

# Probe on INVERSIONES DORALEX (11) if present, else first DO company.
probe_company = env["res.company"].browse(11)
if not probe_company.exists() or not probe_company.active:
    probe_company = env["res.company"].search(
        [("account_fiscal_country_id.code", "=", "DO")], limit=1
    )
company = probe_company
env = env(
    context=dict(
        env.context,
        allowed_company_ids=[company.id],
        justech_approval_skip=True,
        **ctx_mail,
    )
)
Move = env["account.move"].with_company(company)
Tax = env["account.tax"].with_company(company)
Partner = env["res.partner"].with_company(company)
Product = env["product.product"].with_company(company)
sale_j = env["account.journal"].search(
    [("company_id", "=", company.id), ("type", "=", "sale"), ("active", "=", True)],
    limit=1,
)
purch_j = env["account.journal"].search(
    [("company_id", "=", company.id), ("type", "=", "purchase"), ("active", "=", True)],
    limit=1,
)
taxes = Tax.search(
    [
        ("company_id", "=", company.id),
        ("type_tax_use", "=", "sale"),
        ("amount", "=", 18),
        ("active", "=", True),
    ],
    limit=1,
)
ptax = Tax.search(
    [
        ("company_id", "=", company.id),
        ("type_tax_use", "=", "purchase"),
        ("amount", "=", 18),
        ("active", "=", True),
    ],
    limit=1,
)
cust = Partner.search([("name", "=", "DXQA Customer Doralex")], limit=1)
if not cust:
    cust = Partner.create(
        {
            "name": "DXQA Customer Doralex",
            "company_id": company.id,
            "vat": "131000011",
            "country_id": env.ref("base.do").id,
            "is_company": True,
            "customer_rank": 1,
        }
    )
vend = Partner.search([("name", "=", "DXQA Vendor Doralex")], limit=1)
if not vend:
    vend = Partner.create(
        {
            "name": "DXQA Vendor Doralex",
            "company_id": company.id,
            "vat": "132000011",
            "country_id": env.ref("base.do").id,
            "is_company": True,
            "supplier_rank": 1,
        }
    )
prod = Product.search([("default_code", "=", "DXQA-DORALEX")], limit=1)
if not prod:
    prod = Product.create(
        {
            "name": "DXQA Product Doralex",
            "default_code": "DXQA-DORALEX",
            "list_price": 10000,
            "standard_price": 6000,
            "type": "consu",
            "company_id": company.id,
            "taxes_id": [(6, 0, taxes.ids)] if taxes else False,
            "supplier_taxes_id": [(6, 0, ptax.ids)] if ptax else False,
        }
    )
doc_b01 = False
if "justech.do.fiscal.document.type" in env:
    doc_b01 = env["justech.do.fiscal.document.type"].search(
        [("prefix", "=", "B01")], limit=1
    )

existing = Move.search([("ref", "=", "DXQA-PROBE-SALE")], limit=1)
if existing:
    data["probe"]["sale"] = {
        "id": existing.id,
        "state": existing.state,
        "total": existing.amount_total,
        "residual": existing.amount_residual,
        "ncf": getattr(existing, "justech_do_ncf", None),
        "skipped": "already_exists",
    }
else:
    line_vals = {
        "product_id": prod.id,
        "name": "DXQA probe sale",
        "quantity": 1,
        "price_unit": 10000,
    }
    if taxes:
        line_vals["tax_ids"] = [(6, 0, taxes.ids)]
    vals = {
        "move_type": "out_invoice",
        "company_id": company.id,
        "partner_id": cust.id,
        "journal_id": sale_j.id,
        "invoice_date": "2026-08-15",
        "invoice_line_ids": [(0, 0, line_vals)],
        "ref": "DXQA-PROBE-SALE",
    }
    if "justech_do_document_type_id" in Move._fields and doc_b01:
        vals["justech_do_document_type_id"] = doc_b01.id
    try:
        inv = Move.create(vals)
        inv.action_post()
        data["probe"]["sale"] = {
            "id": inv.id,
            "state": inv.state,
            "name": inv.name,
            "total": inv.amount_total,
            "residual": inv.amount_residual,
            "payment_state": inv.payment_state,
            "ncf": getattr(inv, "justech_do_ncf", None),
            "tax": inv.amount_tax,
        }
    except Exception as e:
        env.cr.rollback()
        data["probe"]["sale"] = {"error": "%s: %s" % (type(e).__name__, e)}

existing_b = Move.search([("ref", "=", "DXQA-PROBE-BILL")], limit=1)
if existing_b:
    data["probe"]["bill"] = {
        "id": existing_b.id,
        "state": existing_b.state,
        "total": existing_b.amount_total,
        "skipped": "already_exists",
    }
else:
    vline = {
        "product_id": prod.id,
        "name": "DXQA probe bill",
        "quantity": 1,
        "price_unit": 8000,
    }
    if ptax:
        vline["tax_ids"] = [(6, 0, ptax.ids)]
    bvals = {
        "move_type": "in_invoice",
        "company_id": company.id,
        "partner_id": vend.id,
        "journal_id": purch_j.id,
        "invoice_date": "2026-08-15",
        "invoice_line_ids": [(0, 0, vline)],
        "ref": "DXQA-PROBE-BILL",
    }
    if "l10n_latam_document_number" in Move._fields:
        bvals["l10n_latam_document_number"] = "B0100888011"
    if "justech_do_ncf" in Move._fields:
        bvals["justech_do_ncf"] = "B0100888011"
    if "justech_do_document_type_id" in Move._fields and doc_b01:
        bvals["justech_do_document_type_id"] = doc_b01.id
    try:
        bill = Move.create(bvals)
        bill.action_post()
        data["probe"]["bill"] = {
            "id": bill.id,
            "state": bill.state,
            "name": bill.name,
            "total": bill.amount_total,
            "residual": bill.amount_residual,
            "ncf": getattr(bill, "justech_do_ncf", None),
            "tax": bill.amount_tax,
        }
    except Exception as e:
        env.cr.rollback()
        data["probe"]["bill"] = {"error": "%s: %s" % (type(e).__name__, e)}

env.cr.commit()
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, default=str)
print("INVENTORY_WRITTEN", OUT)
print("QWEB", data["qweb_alexander"])
print("COMPANIES", len(data["companies"]))
print("NCF_RANGES", len(data["ncf_ranges"]))
print("WITHHOLD", len(data["withholding_configs"]))
print("REVERSAL_METHODS", data.get("reversal_methods"))
print("PROBE", json.dumps(data["probe"], default=str))
