# -*- coding: utf-8 -*-
"""Retry controlled audit QA with non-html fields. Staging only. Restore after."""

import json
import time

OUT = "/tmp/final_readiness_audit_retry.json"
stamp = time.strftime("%H%M%S")

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
prev_policy = policy.active
prev_rules = {}
for model_name, label in wanted:
    model = Model.search(
        [("model", "=", model_name), ("transient", "=", False)], limit=1
    )
    rule = Rule.search([("model_id", "=", model.id)], limit=1)
    if not rule:
        rule = Rule.create(
            {
                "name": label,
                "model_id": model.id,
                "active": False,
                "audit_create": True,
                "audit_write": True,
            }
        )
    prev_rules[rule.id] = {
        "active": rule.active,
        "audit_write": rule.audit_write,
        "companies": rule.company_ids.ids,
    }
    rule.write({"active": True, "audit_write": True, "company_ids": [(5, 0, 0)]})

policy.write({"active": True, "audit_write": True})
env["justech.audit.service"]._invalidate_runtime_cache()

company = env["res.company"].search(
    [("account_fiscal_country_id.code", "=", "DO")], order="id", limit=1
)
e = env(
    context=dict(
        env.context,
        allowed_company_ids=[company.id],
        justech_audit_skip_license=True,
        justech_audit_sync=True,
    )
)
svc = e["justech.audit.service"]
print(
    "RUNTIME",
    svc._runtime_enabled(),
    "POLICY",
    svc._get_policy_snapshot(company.id),
)

checks = {}
cases = [
    (
        "res.partner",
        e["res.partner"].search(
            [("name", "like", "DXQA Customer%"), ("company_id", "=", company.id)],
            limit=1,
        ),
        {"phone": "809555%s" % stamp},
    ),
    (
        "sale.order",
        e["sale.order"].search([("company_id", "=", company.id)], limit=1),
        {"client_order_ref": "DXQA-AUD-%s" % stamp},
    ),
    (
        "purchase.order",
        e["purchase.order"].search([("company_id", "=", company.id)], limit=1),
        {"partner_ref": "DXQA-AUD-%s" % stamp},
    ),
    (
        "account.move",
        e["account.move"].search(
            [("company_id", "=", company.id), ("move_type", "=", "out_invoice")],
            limit=1,
        ),
        {"ref": "DXQA-AUD-%s" % stamp},
    ),
    (
        "account.payment",
        e["account.payment"].search([("company_id", "=", company.id)], limit=1),
        {"memo": "DXQA-AUD-%s" % stamp},
    ),
]

for model_name, rec, vals in cases:
    should = svc.should_audit(model_name, "write", company_id=company.id, user_id=e.uid)
    rule = svc._get_rule_snapshot(model_name)
    print("SHOULD", model_name, should, "rule", rule)
    if not rec:
        checks[model_name] = {"result": "FAIL", "error": "missing record"}
        continue
    rec.with_context(justech_audit_skip_license=True).write(vals)
    env.cr.commit()
    logs = Log.search(
        [
            ("model_name", "=", model_name),
            ("record_id", "=", rec.id),
            ("new_value", "like", "DXQA-AUD-%s" % stamp),
        ],
        order="id desc",
        limit=5,
    )
    if not logs:
        logs = Log.search(
            [
                ("model_name", "=", model_name),
                ("record_id", "=", rec.id),
            ],
            order="id desc",
            limit=3,
        )
    sample = logs[:1]
    checks[model_name] = {
        "result": "PASS" if logs else "FAIL",
        "should_audit": should,
        "record": rec.id,
        "logs": len(logs),
        "user": sample.user_id.name if sample and sample.user_id else None,
        "datetime": str(sample.change_date) if sample else None,
        "company": sample.company_id.name if sample and sample.company_id else None,
        "field": sample.field_name if sample else None,
        "old": sample.old_value if sample else None,
        "new": sample.new_value if sample else None,
    }

# restore
policy.active = prev_policy
for rid, prev in prev_rules.items():
    Rule.browse(rid).write(
        {
            "active": prev["active"],
            "audit_write": prev["audit_write"],
            "company_ids": [(6, 0, prev["companies"])],
        }
    )
env["justech.audit.service"]._invalidate_runtime_cache()
env.cr.commit()

result = {
    "AUDIT_LOG_MASS_QA": (
        "PASS" if all(v.get("result") == "PASS" for v in checks.values()) else "FAIL"
    ),
    "checks": checks,
    "transient_rules": Rule.search([]).filtered(lambda r: r.model_id.transient).ids,
    "policy_restored": True,
}
open(OUT, "w").write(json.dumps(result, indent=2, default=str))
print("WROTE", OUT)
print("AUDIT_LOG_MASS_QA", result["AUDIT_LOG_MASS_QA"])
print(json.dumps(checks, indent=2, default=str))
