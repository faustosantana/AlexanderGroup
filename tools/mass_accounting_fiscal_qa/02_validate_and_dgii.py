# -*- coding: utf-8 -*-
"""Validate mass QA set + generate DGII 606/607/608 on STAGING. No prod. No e-CF."""

import json
import os
import time

TAG = "DXQA-MASS-20260831"
OUT = "/tmp/mass_qa_validate.json"
PERIOD = "202608"
DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-31"
os.makedirs("/tmp/mass_qa_files", exist_ok=True)

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

result = {
    "tag": TAG,
    "companies": {},
    "qweb_before": env["ir.ui.view"].search_count(
        [("key", "like", "justech_alexander%")]
    ),
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def _moves(company, move_type):
    return env["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", move_type),
            ("ref", "like", "%s-C%s-" % (TAG, company.id)),
            ("state", "=", "posted"),
        ]
    )


def generate_dgii(company, report_type):
    rec = {
        "type": report_type,
        "result": "NOT_APPLICABLE",
        "lines": 0,
        "errors": [],
    }
    if company.account_fiscal_country_id.code != "DO":
        return rec
    if "justech.do.fiscal.report" not in env:
        rec["result"] = "FAIL"
        rec["errors"].append("model missing")
        return rec
    t0 = time.time()
    try:
        Report = env["justech.do.fiscal.report"].with_company(company)
        vals = {
            "report_type": report_type,
            "company_id": company.id,
            "date_from": DATE_FROM,
            "date_to": DATE_TO,
        }
        if "period_code" in Report._fields:
            vals["period_code"] = PERIOD
        if "name" in Report._fields:
            vals["name"] = "DXQA %s %s C%s" % (report_type, PERIOD, company.id)
        report = Report.create(vals)
        report.action_generate()
        rec["report_id"] = report.id
        rec["state"] = report.state
        rec["lines"] = len(report.line_ids) if "line_ids" in report._fields else 0
        rec["seconds"] = round(time.time() - t0, 2)
        # export files
        for meth, ext in (
            ("action_export_csv", "csv"),
            ("action_export_xlsx", "xlsx"),
            ("action_export_dgii", "bin"),
        ):
            if not hasattr(report, meth):
                continue
            try:
                action = getattr(report, meth)()
                rec["export_%s" % ext] = str(type(action))
                # persist binary fields if present
                for fname in report._fields:
                    if (
                        "file" in fname
                        or "xlsx" in fname
                        or "csv" in fname
                        or "datas" in fname
                    ):
                        data = report[fname]
                        if data:
                            path = "/tmp/mass_qa_files/C%s_%s_%s.bin" % (
                                company.id,
                                report_type,
                                fname,
                            )
                            import base64

                            raw = data
                            if isinstance(raw, str):
                                raw = base64.b64decode(raw)
                            open(path, "wb").write(raw)
                            rec["file_%s" % fname] = path
                            rec["file_%s_size" % fname] = len(raw)
            except Exception as exc:
                rec["errors"].append("%s: %s: %s" % (meth, type(exc).__name__, exc))
        rec["result"] = "PASS" if rec["lines"] >= 0 and not rec["errors"] else "FAIL"
        if rec["errors"] and rec["lines"] == 0:
            rec["result"] = "FAIL"
    except Exception as exc:
        rec["result"] = "FAIL"
        rec["errors"].append("%s: %s" % (type(exc).__name__, exc))
        env.cr.rollback()
    return rec


for company in env["res.company"].search([("active", "=", True)], order="id"):
    e = env(context=dict(env.context, allowed_company_ids=[company.id], **ctx_mail))
    sales = _moves(company, "out_invoice")
    bills = _moves(company, "in_invoice")
    refunds = _moves(company, "out_refund") | _moves(company, "in_refund")
    pays = e["account.payment"].search(
        [
            ("company_id", "=", company.id),
            "|",
            ("memo", "like", "%s-C%s-" % (TAG, company.id)),
            ("payment_reference", "like", "%s-C%s-" % (TAG, company.id)),
        ]
    )
    qa_moves = sales | bills | refunds
    unbalanced = 0
    for mv in qa_moves:
        if abs(sum(mv.line_ids.mapped("balance"))) > 0.05:
            unbalanced += 1
    cross = (
        e["account.move.line"].search_count(
            [
                ("move_id", "in", qa_moves.ids),
                ("company_id", "!=", company.id),
            ]
        )
        if qa_moves
        else 0
    )
    ar_open = sum(sales.mapped("amount_residual"))
    ap_open = sum(bills.mapped("amount_residual"))
    ar_total = sum(sales.mapped("amount_total"))
    ap_total = sum(bills.mapped("amount_total"))
    paid_sales = sales.filtered(lambda m: m.payment_state == "paid")
    partial_sales = sales.filtered(lambda m: m.payment_state == "partial")
    multi_pays = pays.filtered(lambda p: len(p.justech_applied_invoice_ids) > 1)
    receipt_ok = True
    receipt_notes = []
    for p in multi_pays:
        if len(p.justech_applied_invoice_ids) < 2:
            receipt_ok = False
        if not p.justech_applied_invoice_html:
            receipt_ok = False
            receipt_notes.append("payment %s missing applied html" % p.id)
        # render PDF
        try:
            t0 = time.time()
            pdf = e["ir.actions.report"]._render_qweb_pdf(
                "account.action_report_payment_receipt", p.ids
            )
            data = pdf[0] if isinstance(pdf, (list, tuple)) else pdf
            path = "/tmp/mass_qa_files/C%s_receipt_%s.pdf" % (company.id, p.id)
            open(path, "wb").write(data)
            receipt_notes.append(
                "pdf %s bytes=%s sec=%.2f invoices=%s"
                % (
                    p.id,
                    len(data),
                    time.time() - t0,
                    len(p.justech_applied_invoice_ids),
                )
            )
        except Exception as exc:
            receipt_ok = False
            receipt_notes.append("pdf fail %s: %s" % (p.id, exc))

    rec = {
        "name": company.name,
        "fiscal_country": (
            company.account_fiscal_country_id.code
            if company.account_fiscal_country_id
            else None
        ),
        "sales": len(sales),
        "bills": len(bills),
        "credit_notes": len(refunds),
        "payments": len(pays),
        "customer_payments": len(pays.filtered(lambda p: p.partner_type == "customer")),
        "vendor_payments": len(pays.filtered(lambda p: p.partner_type == "supplier")),
        "paid_sales": len(paid_sales),
        "partial_sales": len(partial_sales),
        "ar_total": ar_total,
        "ar_open": ar_open,
        "ap_total": ap_total,
        "ap_open": ap_open,
        "unbalanced_moves": unbalanced,
        "cross_company_lines": cross,
        "multi_invoice_payments": len(multi_pays),
        "multi_invoice_single_receipt": (
            "PASS" if multi_pays and receipt_ok else ("FAIL" if pays else "FAIL")
        ),
        "receipt_notes": receipt_notes,
        "ncf_sales": [
            getattr(m, "justech_do_ncf", None)
            for m in sales
            if getattr(m, "justech_do_ncf", None)
        ],
        "voided": [
            getattr(m, "justech_do_ncf", None)
            for m in sales
            if getattr(m, "justech_do_ncf_voided", False)
        ],
        "dgii": {},
    }
    # unique NCF
    ncfs = [n for n in rec["ncf_sales"] if n]
    rec["ncf_unique"] = len(ncfs) == len(set(ncfs))
    rec["ncf_count"] = len(ncfs)

    if rec["fiscal_country"] == "DO":
        for rtype in ("606", "607", "608", "609", "623"):
            rec["dgii"][rtype] = generate_dgii(company, rtype)
            env.cr.commit()
    else:
        for rtype in ("606", "607", "608", "609", "623"):
            rec["dgii"][rtype] = {"result": "NOT_APPLICABLE"}

    rec["result"] = (
        "PASS"
        if rec["sales"] >= 40
        and rec["bills"] >= 40
        and rec["unbalanced_moves"] == 0
        and rec["cross_company_lines"] == 0
        else "FAIL"
    )
    result["companies"][str(company.id)] = rec
    print(
        "VALIDATE",
        company.id,
        rec["sales"],
        rec["bills"],
        rec["payments"],
        rec["unbalanced_moves"],
        rec["result"],
        {k: v.get("result") for k, v in rec["dgii"].items()},
    )

result["qweb_after"] = env["ir.ui.view"].search_count(
    [("key", "like", "justech_alexander%")]
)
result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2, default=str)
print("VALIDATE_WRITTEN", OUT)
print("QWEB", result["qweb_before"], result["qweb_after"])
