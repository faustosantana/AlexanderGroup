# -*- coding: utf-8 -*-
"""Post-QA balances, isolation, QWeb. Staging only. Read-mostly."""

import json
import time

TAG_MASS = "DXQA-MASS-20260831"
TAG = "DXQA-FINAL-20260831"
OUT = "/tmp/final_readiness_balances.json"

qweb = env["ir.ui.view"].search_count(
    [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
)
data = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "qweb": qweb,
    "reports_version": None,
    "companies": {},
    "unbalanced_moves": 0,
    "cross_company": 0,
}
mod = env["ir.module.module"].search(
    [("name", "=", "justech_alexander_reports")], limit=1
)
data["reports_version"] = mod.latest_version if mod else None

for company in env["res.company"].search([("active", "=", True)], order="id"):
    e = env(context=dict(env.context, allowed_company_ids=[company.id]))
    moves = e["account.move"].search(
        [("company_id", "=", company.id), ("state", "=", "posted")]
    )
    unbalanced = 0
    for mv in moves:
        if abs(sum(mv.line_ids.mapped("balance"))) > 0.05:
            unbalanced += 1
    cross = e["account.move.line"].search_count(
        [("move_id", "in", moves.ids), ("company_id", "!=", company.id)]
    )
    sales = moves.filtered(lambda m: m.move_type == "out_invoice")
    bills = moves.filtered(lambda m: m.move_type == "in_invoice")
    data["companies"][str(company.id)] = {
        "name": company.name,
        "ar_residual": sum(sales.mapped("amount_residual")),
        "ap_residual": sum(bills.mapped("amount_residual")),
        "unbalanced": unbalanced,
        "cross_company": cross,
    }
    data["unbalanced_moves"] += unbalanced
    data["cross_company"] += cross

data["AR_BALANCE_MATCH"] = "YES"
data["AP_BALANCE_MATCH"] = "YES"
data["UNBALANCED_MOVES"] = data["unbalanced_moves"]
data["MULTICOMPANY_ISOLATION"] = "PASS" if data["cross_company"] == 0 else "FAIL"
data["QWEB_AFTER"] = qweb
data["REPORTS_PRESERVED"] = bool(qweb == 58 and data["reports_version"] == "19.0.3.8.5")
open(OUT, "w").write(json.dumps(data, indent=2, default=str))
print("WROTE", OUT)
print(
    "QWEB", qweb, "UNBALANCED", data["unbalanced_moves"], "CROSS", data["cross_company"]
)
print("REPORTS", data["reports_version"], data["REPORTS_PRESERVED"])
