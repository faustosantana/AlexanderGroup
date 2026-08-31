# -*- coding: utf-8 -*-
"""QA outstanding (existing accounts only) + native payments + receipt PDFs.

STAGING only. Never force_payment_move. Never create accounts.
Never touch production.
"""

import json
import time

TAG_MASS = "DXQA-MASS-20260831"
TAG = "DXQA-FINAL-20260831"
PAY_DATE = "2026-08-28"
INV_DATE = "2026-08-15"
OUT = "/tmp/final_readiness_payments.json"
PDF_DIR = "/tmp/final_readiness_files"

import os

os.makedirs(PDF_DIR, exist_ok=True)

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

result = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "prod_touched": False,
    "alexander_confirmation_required": True,
    "force_payment_move_used": False,
    "companies": {},
    "errors": [],
}

RECEIPT_NEEDLES = (
    "FACTURA",
    "NCF",
    "FECHA FACTURA",
    "FECHA VENCIMIENTO",
    "MONTO ORIGINAL",
    "SALDO ANTES",
    "MONTO APLICADO",
    "SALDO RESULTANTE",
    "TOTAL RECIBIDO",
    "TOTAL APLICADO",
    "SALDO NO APLICADO",
)


def _find_outstanding_account(e, company, direction):
    Account = e["account.account"].with_company(company)
    if "company_ids" in Account._fields:
        company_domain = [("company_ids", "in", [company.id])]
    else:
        company_domain = [("company_id", "=", company.id)]
    needles = (
        ["Outstanding Receipt", "Outstanding Receipts"]
        if direction == "inbound"
        else ["Outstanding Payment", "Outstanding Payments"]
    )
    for needle in needles:
        acc = Account.search(company_domain + [("name", "ilike", needle)], limit=1)
        if acc:
            return acc
    journal = e["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", "bank")], limit=1
    )
    if journal and hasattr(journal, "_get_outstanding_account"):
        try:
            acc = journal._get_outstanding_account(direction)
            if acc:
                return acc
        except Exception:
            pass
    return Account


def _open_invoices(e, company, partner, move_types):
    return e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("commercial_partner_id", "=", partner.commercial_partner_id.id),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("move_type", "in", move_types),
            ("amount_residual", ">", 0),
            (
                ("justech_do_ncf_voided", "!=", True)
                if "justech_do_ncf_voided" in e["account.move"]._fields
                else (1, "=", 1)
            ),
        ],
        order="invoice_date asc, id asc",
    )


def _pay_native(e, company, partner, partner_type, journal, method, moves_amounts, ref):
    Wizard = e["multi.invoice.manual.payment.wizard"].with_company(company)
    lines = []
    total = 0.0
    for move, amount in moves_amounts:
        if not move or amount <= 0:
            continue
        lines.append(
            (
                0,
                0,
                {
                    "move_id": move.id,
                    "currency_id": move.currency_id.id,
                    "invoice_date": move.invoice_date,
                    "due_date": move.invoice_date_due,
                    "amount_total": abs(move.amount_total),
                    "amount_residual": abs(move.amount_residual),
                    "amount_to_apply": amount,
                },
            )
        )
        total += amount
    if not lines:
        raise ValueError("no lines for %s" % ref)
    wiz = Wizard.create(
        {
            "partner_type": partner_type,
            "partner_id": partner.id,
            "company_id": company.id,
            "payment_date": PAY_DATE,
            "journal_id": journal.id,
            "payment_method_line_id": method.id,
            "ref": ref,
            "amount_received": total,
            "line_ids": lines,
        }
    )
    action = wiz.action_create_payment()
    return e["account.payment"].browse(action.get("res_id"))


def _render_receipt(e, payment, label):
    html = payment.justech_applied_invoice_html or ""
    missing = [n for n in RECEIPT_NEEDLES if n not in html]
    if payment.partner_type == "supplier" and "FACTURA PROVEEDOR" not in html:
        missing.append("FACTURA PROVEEDOR")
    payload = payment._justech_receipt_payload()
    pdf_path = "%s/%s.pdf" % (PDF_DIR, label)
    html_path = "%s/%s.html" % (PDF_DIR, label)
    open(html_path, "w").write(html)
    pdf_bytes = 0
    try:
        rendered = e["ir.actions.report"]._render_qweb_pdf(
            "account.action_report_payment_receipt", payment.ids
        )
        data = rendered[0] if isinstance(rendered, (list, tuple)) else rendered
        open(pdf_path, "wb").write(data)
        pdf_bytes = len(data)
        qweb_html = e["ir.actions.report"]._render_qweb_html(
            "account.action_report_payment_receipt", payment.ids
        )
        qhtml = qweb_html[0] if isinstance(qweb_html, (list, tuple)) else qweb_html
        if isinstance(qhtml, bytes):
            qhtml = qhtml.decode("utf-8", "replace")
        open(html_path, "w").write(qhtml)
        missing_qweb = [n for n in RECEIPT_NEEDLES if n not in qhtml]
    except Exception as exc:
        missing_qweb = ["PDF:%s:%s" % (type(exc).__name__, exc)]
        qhtml = ""
    return {
        "payment_id": payment.id,
        "invoices": len(payment.justech_applied_invoice_ids),
        "amount": payment.amount,
        "has_move": bool(payment.move_id),
        "html_missing": missing,
        "qweb_missing": missing_qweb,
        "payload_rows": len(payload.get("rows") or []),
        "pdf_bytes": pdf_bytes,
        "pdf_path": pdf_path,
        "single_receipt": len(payment.justech_applied_invoice_ids)
        == len(payload.get("rows") or []),
    }


def _ledger_residual(e, company, partner, account_types):
    lines = e["account.move.line"].search(
        [
            ("company_id", "=", company.id),
            ("partner_id", "=", partner.commercial_partner_id.id),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "in", account_types),
            ("reconciled", "=", False),
        ]
    )
    return sum(lines.mapped("amount_residual"))


for company in env["res.company"].search([("active", "=", True)], order="id"):
    rec = {
        "name": company.name,
        "assigned": [],
        "native": {},
        "receipts": [],
        "errors": [],
        "confirmation_required": True,
    }
    e = env(
        context=dict(
            env.context,
            allowed_company_ids=[company.id],
            justech_approval_skip=True,
            **ctx_mail,
        )
    )
    bank = e["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", "bank")], limit=1
    )
    inbound = e["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "inbound"),
        ],
        limit=1,
    )
    outbound = e["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "outbound"),
        ],
        limit=1,
    )
    in_acc = _find_outstanding_account(e, company, "inbound")
    out_acc = _find_outstanding_account(e, company, "outbound")
    rec["existing_accounts"] = {
        "inbound": in_acc.display_name if in_acc else None,
        "outbound": out_acc.display_name if out_acc else None,
    }
    if in_acc and inbound and not inbound.payment_account_id:
        inbound.payment_account_id = in_acc.id
        rec["assigned"].append(
            {"line": inbound.id, "account": in_acc.id, "direction": "inbound"}
        )
    if out_acc and outbound and not outbound.payment_account_id:
        outbound.payment_account_id = out_acc.id
        rec["assigned"].append(
            {"line": outbound.id, "account": out_acc.id, "direction": "outbound"}
        )
    rec["inbound_configured"] = bool(inbound and inbound.payment_account_id)
    rec["outbound_configured"] = bool(outbound and outbound.payment_account_id)

    cust = e["res.partner"].search(
        [("name", "like", "DXQA Customer%"), ("company_id", "=", company.id)],
        limit=1,
    )
    vend = e["res.partner"].search(
        [("name", "like", "DXQA Vendor%"), ("company_id", "=", company.id)],
        limit=1,
    )
    if not cust or not vend or not bank:
        rec["errors"].append("missing partner/journal")
        result["companies"][str(company.id)] = rec
        continue

    open_sales = _open_invoices(e, company, cust, ["out_invoice"])
    open_bills = _open_invoices(e, company, vend, ["in_invoice"])
    rec["open_sales"] = len(open_sales)
    rec["open_bills"] = len(open_bills)

    def _safe(key, fn):
        try:
            with e.cr.savepoint():
                rec["native"][key] = fn()
        except Exception as exc:
            rec["errors"].append("%s: %s: %s" % (key, type(exc).__name__, exc))
            rec["native"][key] = {"result": "FAIL", "error": str(exc)}

    if rec["inbound_configured"] and len(open_sales) >= 1:
        inv = open_sales[0]
        before = inv.amount_residual

        def _full():
            pay = _pay_native(
                e,
                company,
                cust,
                "customer",
                bank,
                inbound,
                [(inv, inv.amount_residual)],
                "%s-C%s-PAY-C-FULL" % (TAG, company.id),
            )
            inv.invalidate_recordset()
            return {
                "payment_id": pay.id,
                "move": bool(pay.move_id),
                "before": before,
                "applied": pay.amount,
                "after": inv.amount_residual,
                "result": "PASS" if pay.move_id else "FAIL",
            }

        _safe("customer_full", _full)

    if rec["inbound_configured"] and len(open_sales) >= 2:
        inv = open_sales[1]
        before = inv.amount_residual
        apply = round(min(before * 0.4, before - 1), 2) if before > 2 else before / 2

        def _part():
            pay = _pay_native(
                e,
                company,
                cust,
                "customer",
                bank,
                inbound,
                [(inv, apply)],
                "%s-C%s-PAY-C-PART" % (TAG, company.id),
            )
            inv.invalidate_recordset()
            return {
                "payment_id": pay.id,
                "move": bool(pay.move_id),
                "before": before,
                "applied": apply,
                "after": inv.amount_residual,
                "match": abs((before - apply) - inv.amount_residual) < 0.05,
                "result": "PASS" if pay.move_id else "FAIL",
            }

        _safe("customer_partial", _part)

    open_sales = _open_invoices(e, company, cust, ["out_invoice"])
    for n in (2, 3, 4, 5):
        if not rec["inbound_configured"] or len(open_sales) < n:
            rec["native"]["customer_multi_%s" % n] = {
                "result": "SKIP",
                "reason": "need %s open sales, have %s" % (n, len(open_sales)),
            }
            continue
        group = open_sales[:n]
        amounts = [(m, m.amount_residual) for m in group]

        def _multi(group=group, amounts=amounts, n=n):
            pay = _pay_native(
                e,
                company,
                cust,
                "customer",
                bank,
                inbound,
                amounts,
                "%s-C%s-PAY-C-M%s" % (TAG, company.id, n),
            )
            info = _render_receipt(e, pay, "C%s_receipt_multi%s" % (company.id, n))
            info["result"] = (
                "PASS"
                if pay.move_id
                and info["invoices"] == n
                and not info["html_missing"]
                and not info["qweb_missing"]
                else "FAIL"
            )
            return info

        _safe("customer_multi_%s" % n, _multi)
        open_sales = _open_invoices(e, company, cust, ["out_invoice"])

    if rec["inbound_configured"] and len(open_sales) >= 2:
        a, b = open_sales[0], open_sales[1]
        apply_a = round(min(a.amount_residual * 0.5, a.amount_residual), 2)
        apply_b = round(min(b.amount_residual * 0.3, b.amount_residual), 2)

        def _mpart():
            pay = _pay_native(
                e,
                company,
                cust,
                "customer",
                bank,
                inbound,
                [(a, apply_a), (b, apply_b)],
                "%s-C%s-PAY-C-MPART" % (TAG, company.id),
            )
            info = _render_receipt(e, pay, "C%s_receipt_partial_multi" % company.id)
            info["result"] = (
                "PASS"
                if pay.move_id and info["invoices"] == 2 and not info["qweb_missing"]
                else "FAIL"
            )
            return info

        _safe("customer_partial_multi", _mpart)

    open_bills = _open_invoices(e, company, vend, ["in_invoice"])
    if rec["outbound_configured"] and len(open_bills) >= 3:
        group = open_bills[:3]
        amounts = [(m, m.amount_residual) for m in group]

        def _vend():
            pay = _pay_native(
                e,
                company,
                vend,
                "supplier",
                bank,
                outbound,
                amounts,
                "%s-C%s-PAY-V-M3" % (TAG, company.id),
            )
            info = _render_receipt(e, pay, "C%s_vendor_receipt_multi3" % company.id)
            info["result"] = (
                "PASS"
                if pay.move_id
                and info["invoices"] == 3
                and "FACTURA PROVEEDOR"
                in open(
                    "%s/C%s_vendor_receipt_multi3.html" % (PDF_DIR, company.id)
                ).read()
                else "FAIL"
            )
            return info

        _safe("vendor_multi_3", _vend)

    # Re-render existing mass multi payments (company 11 evidence + all).
    existing_multi = e["account.payment"].search(
        [
            ("company_id", "=", company.id),
            "|",
            ("memo", "like", "%s-C%s-PAY-" % (TAG_MASS, company.id)),
            ("payment_reference", "like", "%s-C%s-PAY-" % (TAG_MASS, company.id)),
        ]
    )
    existing_multi = existing_multi.filtered(
        lambda p: len(p.justech_applied_invoice_ids) >= 2
    )
    for pay in existing_multi[:6]:
        rec["receipts"].append(
            _render_receipt(e, pay, "C%s_existing_%s" % (company.id, pay.id))
        )

    ar_moves = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
    )
    ap_moves = e["account.move"].search(
        [
            ("company_id", "=", company.id),
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
        ]
    )
    rec["ar_residual_invoices"] = sum(ar_moves.mapped("amount_residual"))
    rec["ap_residual_invoices"] = sum(ap_moves.mapped("amount_residual"))
    rec["ar_ledger"] = _ledger_residual(e, company, cust, ["asset_receivable"])
    rec["ap_ledger"] = _ledger_residual(e, company, vend, ["liability_payable"])
    rec["unbalanced_qa"] = 0
    for mv in ar_moves | ap_moves:
        if abs(sum(mv.line_ids.mapped("balance"))) > 0.05:
            rec["unbalanced_qa"] += 1
    result["companies"][str(company.id)] = rec
    e.cr.commit()

native_pass = True
receipt_pass = True
vendor_pass = False
for rec in result["companies"].values():
    for key, val in rec.get("native", {}).items():
        if isinstance(val, dict) and val.get("result") == "FAIL":
            native_pass = False
        if key.startswith("customer_multi_") and isinstance(val, dict):
            if val.get("result") == "FAIL":
                receipt_pass = False
        if (
            key == "vendor_multi_3"
            and isinstance(val, dict)
            and val.get("result") == "PASS"
        ):
            vendor_pass = True
    if rec.get("errors"):
        native_pass = False
    if not rec.get("inbound_configured") or not rec.get("outbound_configured"):
        if rec.get("name") and "Plantilla" not in (rec.get("name") or ""):
            native_pass = False

result["OUTSTANDING_CONFIG_QA"] = (
    "PASS"
    if all(
        c.get("inbound_configured") and c.get("outbound_configured")
        for c in result["companies"].values()
        if "Plantilla" not in (c.get("name") or "")
    )
    else "FAIL"
)
result["NATIVE_PAYMENT_FLOW_QA"] = "PASS" if native_pass else "FAIL"
result["MULTI_INVOICE_RECEIPT_PDF"] = "PASS" if receipt_pass else "FAIL"
result["VENDOR_MULTI_INVOICE_RECEIPT_QA"] = "PASS" if vendor_pass else "FAIL"
result["ALEXANDER_CONFIRMATION_REQUIRED"] = True
result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
open(OUT, "w").write(json.dumps(result, indent=2, default=str))
print("WROTE", OUT)
print("OUTSTANDING_CONFIG_QA", result["OUTSTANDING_CONFIG_QA"])
print("NATIVE_PAYMENT_FLOW_QA", result["NATIVE_PAYMENT_FLOW_QA"])
print("MULTI_INVOICE_RECEIPT_PDF", result["MULTI_INVOICE_RECEIPT_PDF"])
print("VENDOR_MULTI_INVOICE_RECEIPT_QA", result["VENDOR_MULTI_INVOICE_RECEIPT_QA"])
