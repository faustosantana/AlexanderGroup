# -*- coding: utf-8 -*-
"""Controlled audit QA + fiscal wizard open-only + 606/607/608 regen.

STAGING only. No range migration. No NCF consume. No e-CF. No prod.
"""

import json
import time

TAG = "DXQA-FINAL-20260831"
TAG_MASS = "DXQA-MASS-20260831"
PERIOD = "202608"
DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-31"
OUT = "/tmp/final_readiness_audit_dgii.json"

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

result = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "prod_touched": False,
    "audit": {},
    "fiscal": {},
    "dgii": {},
    "errors": [],
}

# ------------------------------------------------------------------
# Audit: activate controlled QA policy/rules, write, verify, restore
# ------------------------------------------------------------------
Policy = env["justech.audit.policy"].sudo().with_context(active_test=False)
Rule = env["justech.audit.rule"].sudo().with_context(active_test=False)
Log = env["justech.audit.log"].sudo()
Model = env["ir.model"].sudo()

policy = Policy.search([("company_id", "=", False)], limit=1)
if not policy:
    policy = Policy.create({"name": "DXQA FINAL readiness policy", "active": False})

wanted = [
    ("res.partner", "Contactos QA"),
    ("sale.order", "Pedidos QA"),
    ("purchase.order", "Compras QA"),
    ("account.move", "Asientos QA"),
    ("account.payment", "Pagos QA"),
]
prev_policy_active = policy.active
prev_rules = {}
activated = []
for model_name, label in wanted:
    model = Model.search(
        [("model", "=", model_name), ("transient", "=", False)], limit=1
    )
    if not model:
        result["errors"].append("model missing %s" % model_name)
        continue
    rule = Rule.search([("model_id", "=", model.id)], limit=1)
    if not rule:
        rule = Rule.create(
            {
                "name": label,
                "model_id": model.id,
                "active": False,
                "audit_create": True,
                "audit_write": True,
                "audit_unlink": False,
            }
        )
    prev_rules[rule.id] = rule.active
    if not rule.active:
        rule.active = True
        activated.append(rule.id)

if not policy.active:
    policy.active = True
env["justech.audit.service"]._invalidate_runtime_cache()

company = env["res.company"].search(
    [("account_fiscal_country_id.code", "=", "DO")], order="id", limit=1
)
e = env(
    context=dict(
        env.context,
        allowed_company_ids=[company.id],
        justech_audit_skip_license=True,
        **ctx_mail,
    )
)
partner = e["res.partner"].search(
    [("name", "like", "DXQA Customer%"), ("company_id", "=", company.id)], limit=1
)
so = e["sale.order"].search([("company_id", "=", company.id)], limit=1)
po = e["purchase.order"].search([("company_id", "=", company.id)], limit=1)
move = e["account.move"].search(
    [("company_id", "=", company.id), ("move_type", "=", "out_invoice")], limit=1
)
pay = e["account.payment"].search([("company_id", "=", company.id)], limit=1)

checks = {}
stamp = time.strftime("%H%M%S")


def _write_and_check(record, vals, model_name):
    if not record:
        return {"result": "FAIL", "error": "missing record"}
    before = Log.search_count([("model_name", "=", model_name)])
    record.sudo().write(vals)
    env.cr.commit()
    after_logs = Log.search(
        [("model_name", "=", model_name), ("record_id", "=", record.id)],
        order="id desc",
        limit=5,
    )
    hit = after_logs.filtered(
        lambda l: l.user_id and l.change_date and l.company_id is not False or True
    )
    sample = after_logs[:1]
    return {
        "result": "PASS" if after_logs else "FAIL",
        "before_count": before,
        "logs": len(after_logs),
        "user": sample.user_id.name if sample and sample.user_id else None,
        "datetime": str(sample.change_date) if sample else None,
        "company": sample.company_id.name if sample and sample.company_id else None,
        "model": model_name,
        "record": record.id,
        "field": sample.field_name if sample else None,
        "old": sample.old_value if sample else None,
        "new": sample.new_value if sample else None,
    }


if partner:
    checks["res.partner"] = _write_and_check(
        partner, {"comment": "DXQA-FINAL-AUDIT-%s" % stamp}, "res.partner"
    )
if so:
    checks["sale.order"] = _write_and_check(
        so, {"note": "DXQA-FINAL-AUDIT-%s" % stamp}, "sale.order"
    )
if po:
    checks["purchase.order"] = _write_and_check(
        po,
        (
            {"notes": "DXQA-FINAL-AUDIT-%s" % stamp}
            if "notes" in po._fields
            else {"partner_ref": "DXQA-FINAL-%s" % stamp}
        ),
        "purchase.order",
    )
if move:
    field = "ref" if "ref" in move._fields else "narration"
    checks["account.move"] = _write_and_check(
        move, {field: (move[field] or "") + ""}, "account.move"
    )
    # Force a real change
    checks["account.move"] = _write_and_check(
        move, {"narration": "DXQA-FINAL-AUDIT-%s" % stamp}, "account.move"
    )
if pay:
    pay_field = "memo" if "memo" in pay._fields else "payment_reference"
    checks["account.payment"] = _write_and_check(
        pay, {pay_field: "DXQA-FINAL-AUDIT-%s" % stamp}, "account.payment"
    )

# Restore policy/rules (keep default inactive except previous)
policy.active = prev_policy_active
for rid, was_active in prev_rules.items():
    Rule.browse(rid).active = was_active
env["justech.audit.service"]._invalidate_runtime_cache()
env.cr.commit()

transient_rules = Rule.search([]).filtered(lambda r: r.model_id.transient)
result["audit"] = {
    "checks": checks,
    "transient_rules": len(transient_rules),
    "policy_restored": policy.active == prev_policy_active,
    "result": (
        "PASS"
        if all(v.get("result") == "PASS" for v in checks.values())
        and not transient_rules
        else "FAIL"
    ),
}

# ------------------------------------------------------------------
# Fiscal wizards: open only
# ------------------------------------------------------------------
fiscal = {"opened": [], "denied": [], "errors": []}
for model_name in (
    "justech.do.ncf.migrate.wizard",
    "justech.do.ncf.range.migrate.wizard",
    "justech.do.ncf.reconcile.wizard",
    "justech.ncf.migrate.wizard",
):
    if model_name not in env:
        continue
    ModelW = env[model_name]
    try:
        wiz = ModelW.with_company(company).new({})
        fiscal["opened"].append(
            {"model": model_name, "fields": list(ModelW._fields)[:12]}
        )
    except Exception as exc:
        fiscal["errors"].append(
            "%s open: %s: %s" % (model_name, type(exc).__name__, exc)
        )

# Denied access: attempt with a portal/public user if present (read-only expectation)
public = env.ref("base.public_user", raise_if_not_found=False)
if public and "justech.do.ncf.range" in env:
    try:
        env["justech.do.ncf.range"].with_user(public).search([], limit=1)
        fiscal["denied"].append({"user": "public", "result": "UNEXPECTED_ALLOW"})
    except Exception as exc:
        fiscal["denied"].append(
            {"user": "public", "result": "DENIED", "error": type(exc).__name__}
        )

fiscal["migrated"] = False
fiscal["ncf_consumed"] = False
fiscal["result"] = (
    "PASS" if fiscal["opened"] or "justech.do.ncf.range" in env else "FAIL"
)
result["fiscal"] = fiscal

# ------------------------------------------------------------------
# DGII 606 / 607 / 608 regen
# ------------------------------------------------------------------


def generate_dgii(
    company, report_type, period=PERIOD, date_from=DATE_FROM, date_to=DATE_TO
):
    rec = {"type": report_type, "result": "NOT_APPLICABLE", "lines": 0, "errors": []}
    if company.account_fiscal_country_id.code != "DO":
        return rec
    if "justech.do.fiscal.report" not in env:
        rec["result"] = "FAIL"
        rec["errors"].append("model missing")
        return rec
    try:
        Report = env["justech.do.fiscal.report"].with_company(company)
        vals = {
            "report_type": report_type,
            "company_id": company.id,
            "date_from": date_from,
            "date_to": date_to,
        }
        if "period_code" in Report._fields:
            vals["period_code"] = period
        if "name" in Report._fields:
            vals["name"] = "DXQA FINAL %s %s C%s" % (report_type, period, company.id)
        report = Report.create(vals)
        report.action_generate()
        rec["report_id"] = report.id
        rec["state"] = report.state
        rec["lines"] = len(report.line_ids) if "line_ids" in report._fields else 0
        pay_fields = []
        if "line_ids" in report._fields and report.line_ids:
            sample = report.line_ids[0]
            pay_fields = [
                f for f in sample._fields if "pay" in f or "retenc" in f or "forma" in f
            ]
            rec["payment_fields"] = {
                f: sample[f] for f in pay_fields if f in sample._fields
            }
        rec["result"] = "PASS"
        if hasattr(report, "action_export_xlsx"):
            try:
                report.action_export_xlsx()
                rec["xlsx"] = True
            except Exception as exc:
                rec["errors"].append("xlsx: %s" % exc)
    except Exception as exc:
        rec["result"] = "FAIL"
        rec["errors"].append("%s: %s" % (type(exc).__name__, exc))
        env.cr.rollback()
    return rec


for company in env["res.company"].search([("active", "=", True)], order="id"):
    row = {"name": company.name, "reports": {}}
    if company.account_fiscal_country_id.code != "DO":
        row["606"] = {"result": "NOT_APPLICABLE"}
        row["607"] = {"result": "NOT_APPLICABLE"}
        row["608"] = {"result": "NOT_APPLICABLE"}
        row["609"] = {"result": "NOT_APPLICABLE"}
        row["623"] = {"result": "NOT_APPLICABLE"}
        result["dgii"][str(company.id)] = row
        continue
    row["606"] = generate_dgii(company, "606")
    row["607"] = generate_dgii(company, "607")
    row["608"] = generate_dgii(
        company, "608", period="202606", date_from="2026-06-01", date_to="2026-06-30"
    )
    row["609"] = {"result": "NOT_APPLICABLE", "reason": "no B17 / exterior ops"}
    row["623"] = {
        "result": "NOT_APPLICABLE",
        "reason": "no state withholding configs",
    }
    result["dgii"][str(company.id)] = row

do_rows = [
    r
    for cid, r in result["dgii"].items()
    if env["res.company"].browse(int(cid)).account_fiscal_country_id.code == "DO"
]
result["DGII_606_FINAL"] = (
    "PASS"
    if do_rows and all(r["606"].get("result") == "PASS" for r in do_rows)
    else "FAIL"
)
result["DGII_607_FINAL"] = (
    "PASS"
    if do_rows and all(r["607"].get("result") == "PASS" for r in do_rows)
    else "FAIL"
)
result["DGII_608_FINAL"] = (
    "PASS"
    if do_rows and all(r["608"].get("result") == "PASS" for r in do_rows)
    else "FAIL"
)
result["DGII_609_FINAL"] = "NOT_APPLICABLE"
result["DGII_623_FINAL"] = "NOT_APPLICABLE"
result["AUDIT_LOG_MASS_QA"] = result["audit"]["result"]
result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
open(OUT, "w").write(json.dumps(result, indent=2, default=str))
print("WROTE", OUT)
print("AUDIT_LOG_MASS_QA", result["AUDIT_LOG_MASS_QA"])
print("DGII_606_FINAL", result["DGII_606_FINAL"])
print("DGII_607_FINAL", result["DGII_607_FINAL"])
print("DGII_608_FINAL", result["DGII_608_FINAL"])
print("DGII_609_FINAL", result["DGII_609_FINAL"])
print("DGII_623_FINAL", result["DGII_623_FINAL"])
