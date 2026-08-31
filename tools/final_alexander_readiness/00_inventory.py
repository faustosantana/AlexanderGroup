# -*- coding: utf-8 -*-
"""Inventory for final Alexander readiness. STAGING only. No writes."""

import json
import time

OUT = "/tmp/final_readiness_inventory.json"
QWEB_DOMAIN = [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]

data = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "database": env.cr.dbname,
    "prod_touched": False,
    "qweb_alexander": env["ir.ui.view"].search_count(QWEB_DOMAIN),
    "qweb_keys": env["ir.ui.view"].search(QWEB_DOMAIN).mapped("key"),
    "modules": {},
    "companies": [],
    "outstanding": [],
    "ncf_ranges": [],
    "audit": {},
    "margin_trace": {},
}

for mod in (
    "multi_invoice_manual_payment_prod",
    "justech_alexander_reports",
    "justech_purchase_sale_margin_control",
    "justech_sale_purchase_trace",
    "justech_global_audit_log",
    "justech_l10n_do_reports",
    "justech_approval_flow",
):
    rec = env["ir.module.module"].search([("name", "=", mod)], limit=1)
    data["modules"][mod] = {
        "state": rec.state if rec else "missing",
        "version": rec.latest_version if rec else None,
    }

Account = env["account.account"]
PML = env["account.payment.method.line"]
Journal = env["account.journal"]

for company in env["res.company"].search([("active", "=", True)], order="id"):
    e = env(context=dict(env.context, allowed_company_ids=[company.id]))
    banks = e["account.journal"].search(
        [("company_id", "=", company.id), ("type", "in", ("bank", "cash"))]
    )
    bank_rows = []
    for journal in banks:
        for line in (
            journal.inbound_payment_method_line_ids
            | journal.outbound_payment_method_line_ids
        ):
            ptype = (
                line.payment_method_id.payment_type if line.payment_method_id else None
            )
            acc = line.payment_account_id
            bank_rows.append(
                {
                    "journal_id": journal.id,
                    "journal": journal.display_name,
                    "journal_type": journal.type,
                    "method_line_id": line.id,
                    "method": line.name,
                    "payment_type": ptype,
                    "outstanding_account_id": acc.id if acc else None,
                    "outstanding_account": acc.display_name if acc else None,
                    "status": "CONFIGURED" if acc else "MISSING",
                }
            )
            data["outstanding"].append(
                {
                    "company_id": company.id,
                    "company": company.name,
                    "bank_journal": journal.display_name,
                    "payment_method_line": line.name,
                    "payment_type": ptype,
                    "outstanding_account": acc.display_name if acc else None,
                    "current_status": "CONFIGURED" if acc else "MISSING",
                }
            )
    ncf_left = []
    if "justech.do.ncf.range" in e:
        for rng in e["justech.do.ncf.range"].search([("company_id", "=", company.id)]):
            left = None
            if rng.number_next and rng.number_to:
                left = rng.number_to - rng.number_next + 1
            ncf_left.append(
                {
                    "prefix": rng.prefix if "prefix" in rng._fields else None,
                    "state": rng.state,
                    "number_next": rng.number_next,
                    "number_to": rng.number_to,
                    "remaining": left,
                }
            )
            data["ncf_ranges"].append(
                {
                    "company_id": company.id,
                    "prefix": rng.prefix if "prefix" in rng._fields else None,
                    "state": rng.state,
                    "remaining": left,
                }
            )
    existing_out = []
    if "company_ids" in Account._fields:
        domain = [("company_ids", "in", [company.id])]
    else:
        domain = [("company_id", "=", company.id)]
    for acc in e["account.account"].search(domain + [("name", "ilike", "outstanding")]):
        existing_out.append(
            {
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "account_type": acc.account_type,
            }
        )
    data["companies"].append(
        {
            "id": company.id,
            "name": company.name,
            "vat": company.vat
            or (company.partner_id.vat if company.partner_id else None),
            "currency": company.currency_id.name,
            "fiscal_country": (
                company.account_fiscal_country_id.code
                if company.account_fiscal_country_id
                else None
            ),
            "banks": bank_rows,
            "existing_outstanding_accounts": existing_out,
            "ncf_ranges": ncf_left,
        }
    )

if "justech.audit.policy" in env:
    policies = env["justech.audit.policy"].with_context(active_test=False).search([])
    rules = env["justech.audit.rule"].with_context(active_test=False).search([])
    data["audit"] = {
        "policies": [
            {
                "id": p.id,
                "name": p.name,
                "active": p.active,
                "company_id": p.company_id.id if p.company_id else None,
            }
            for p in policies
        ],
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "model": r.model_name,
                "active": r.active,
                "transient": bool(r.model_id.transient) if r.model_id else None,
            }
            for r in rules
        ],
    }

if "purchase.sale.reconciliation.rule" in env:
    data["margin_trace"]["priority"] = []
    for company in env["res.company"].search([("active", "=", True)]):
        methods = env["purchase.sale.reconciliation.rule"].get_trace_priority(company)
        data["margin_trace"]["priority"].append(
            {"company_id": company.id, "methods": methods}
        )

data["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
open(OUT, "w").write(json.dumps(data, indent=2, default=str))
print("WROTE", OUT)
print("QWEB", data["qweb_alexander"])
print(
    "OUTSTANDING_MISSING",
    sum(1 for r in data["outstanding"] if r["current_status"] == "MISSING"),
)
print("MODULES", json.dumps(data["modules"]))
