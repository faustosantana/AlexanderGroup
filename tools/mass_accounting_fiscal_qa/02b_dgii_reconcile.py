# -*- coding: utf-8 -*-
"""Reconcile DGII reports vs QA accounting. Staging only."""

import json

TAG = "DXQA-MASS-20260831"
OUT = "/tmp/mass_qa_dgii_reconcile.json"
ctx = {"allowed_company_ids": [c.id for c in env["res.company"].search([])]}

data = {"companies": {}}

for company in env["res.company"].search([("active", "=", True)], order="id"):
    e = env(context=dict(env.context, allowed_company_ids=[company.id]))
    sales = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "out_invoice"),
            ("ref", "like", "%s-C%s-S-" % (TAG, company.id)),
            ("state", "=", "posted"),
        ]
    )
    bills = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "in_invoice"),
            ("ref", "like", "%s-C%s-B-" % (TAG, company.id)),
            ("state", "=", "posted"),
        ]
    )
    cn_out = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "out_refund"),
            ("state", "=", "posted"),
            ("create_date", ">=", "2026-08-31 00:00:00"),
        ]
    )
    cn_in = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "in_refund"),
            ("state", "=", "posted"),
            ("create_date", ">=", "2026-08-31 00:00:00"),
        ]
    )
    voids = sales.filtered(lambda m: getattr(m, "justech_do_ncf_voided", False))
    states = {}
    for m in sales:
        states[m.payment_state] = states.get(m.payment_state, 0) + 1
    reports = {}
    if "justech.do.fiscal.report" in e:
        for r in e["justech.do.fiscal.report"].search(
            [("company_id", "=", company.id), ("name", "like", "DXQA %")]
        ):
            line_n = len(r.line_ids) if "line_ids" in r._fields else 0
            amt = 0.0
            itbis = 0.0
            if "line_ids" in r._fields:
                for line in r.line_ids:
                    for f in line._fields:
                        if f in (
                            "amount_total",
                            "total_amount",
                            "invoiced_amount",
                            "billed_amount",
                            "amount",
                        ):
                            amt += float(line[f] or 0)
                        if "itbis" in f or "tax" in f:
                            try:
                                itbis += float(line[f] or 0)
                            except Exception:
                                pass
            reports[r.report_type] = {
                "id": r.id,
                "state": r.state,
                "lines": line_n,
                "period": getattr(r, "period_code", None),
                "date_from": str(r.date_from),
                "date_to": str(r.date_to),
                "sum_amount_guess": amt,
                "sum_itbis_guess": itbis,
            }
    # generate 608 for June (void dates)
    dgii_608 = {"result": "NOT_APPLICABLE"}
    if company.account_fiscal_country_id.code == "DO" and voids:
        try:
            Report = e["justech.do.fiscal.report"]
            vals = {
                "report_type": "608",
                "company_id": company.id,
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            }
            if "period_code" in Report._fields:
                vals["period_code"] = "202606"
            if "name" in Report._fields:
                vals["name"] = "DXQA 608 202606 C%s" % company.id
            r = Report.create(vals)
            r.action_generate()
            dgii_608 = {
                "result": "PASS" if len(r.line_ids) >= len(voids) else "FAIL",
                "lines": len(r.line_ids),
                "voids": [v.justech_do_ncf for v in voids],
                "report_id": r.id,
            }
            e.cr.commit()
        except Exception as exc:
            dgii_608 = {"result": "FAIL", "error": "%s: %s" % (type(exc).__name__, exc)}
            e.cr.rollback()

    rec606 = reports.get("606", {})
    rec607 = reports.get("607", {})
    data["companies"][str(company.id)] = {
        "name": company.name,
        "sales": len(sales),
        "bills": len(bills),
        "cn_out": len(cn_out),
        "cn_in": len(cn_in),
        "voids": len(voids),
        "sales_total": sum(sales.mapped("amount_total")),
        "sales_untaxed": sum(sales.mapped("amount_untaxed")),
        "sales_tax": sum(sales.mapped("amount_tax")),
        "bills_total": sum(bills.mapped("amount_total")),
        "bills_untaxed": sum(bills.mapped("amount_untaxed")),
        "bills_tax": sum(bills.mapped("amount_tax")),
        "payment_states": states,
        "reports": reports,
        "608_june": dgii_608,
        "606_lines_vs_bills": (rec606.get("lines"), len(bills) + len(cn_in)),
        "607_lines_vs_sales": (rec607.get("lines"), len(sales) + len(cn_out)),
    }
    print(
        company.id,
        "S",
        len(sales),
        "B",
        len(bills),
        "CNo",
        len(cn_out),
        "CNi",
        len(cn_in),
        "V",
        len(voids),
        "states",
        states,
        "606",
        rec606.get("lines"),
        "607",
        rec607.get("lines"),
        "608jun",
        dgii_608,
    )

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, default=str)
print("WRITTEN", OUT)
