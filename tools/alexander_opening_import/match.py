"""Cruza Excel (saldos) con PDFs (detalle). No importa si el total no cuadra."""

from __future__ import annotations

from decimal import Decimal

from .normalize import money, norm_ncf, norm_vat
from .total_overrides import PDF_TOTAL_OVERRIDES


def match_invoices(cxc_rows: list[dict], pdf_invoices: list[dict]) -> dict:
    pdf_by_key = {}
    for inv in pdf_invoices:
        key = (inv.get("company"), norm_ncf(inv["ncf"]))
        pdf_by_key.setdefault(key, []).append(inv)

    matched = []
    missing_pdf = []
    blocked = []
    for row in cxc_rows:
        key = (row["company"], norm_ncf(row["ncf"]))
        cands = pdf_by_key.get(key, [])
        if not cands:
            # try ncf-only
            cands = [i for i in pdf_invoices if norm_ncf(i["ncf"]) == row["ncf"]]
            cands = [
                i
                for i in cands
                if not i.get("company") or i.get("company") == row["company"]
            ]
        if not cands:
            rec = dict(row)
            rec["EXCEL_PDF_MATCH"] = "MISSING_PDF"
            rec["SOURCE_DOCUMENT_STATUS"] = "MISSING_PDF"
            missing_pdf.append(rec)
            continue
        inv = cands[0]
        excel_total = money(row["amount_original"])
        pdf_total = money(inv.get("total") or 0)
        vat_ok = True
        if row["vat"] and inv.get("customer_vat"):
            vat_ok = norm_vat(row["vat"]) == norm_vat(inv["customer_vat"])
        status = "PASS"
        reasons = []
        override = PDF_TOTAL_OVERRIDES.get(key)
        override_target = money(override["pdf_total"]) if override else Decimal("0")
        rec_override = bool(override and override_target)
        if rec_override:
            pdf_total = override_target
        if not row["balance_ok"]:
            status = "FAIL"
            reasons.append("EXCEL_BALANCE_EQUATION")
        if (
            pdf_total
            and excel_total
            and abs(pdf_total - excel_total) > Decimal("0.05")
            and not rec_override
        ):
            status = "FAIL"
            reasons.append(f"TOTAL_MISMATCH excel={excel_total} pdf={pdf_total}")
        if not vat_ok:
            status = "FAIL"
            reasons.append("RNC_CONTRADICTORY")
        rec = dict(row)
        rec["pdf"] = inv
        rec["EXCEL_PDF_MATCH"] = status
        rec["match_reasons"] = reasons
        if rec_override and status == "PASS":
            rec["excel_amount_original"] = row["amount_original"]
            rec["excel_amount_residual"] = row["amount_residual"]
            rec["amount_original"] = str(pdf_total)
            rec["amount_residual"] = str(pdf_total - money(row.get("amount_paid") or 0))
            rec["TOTAL_OVERRIDE"] = "PDF"
            rec["override_reason"] = override["reason"]
            reasons.append(
                f"TOTAL_OVERRIDE_PDF excel={excel_total} pdf={pdf_total} "
                f"{override['reason']}"
            )
        if status == "PASS":
            matched.append(rec)
        else:
            blocked.append(rec)

    used = {(i.get("company"), norm_ncf(i["ncf"])) for i in pdf_invoices}
    excel_keys = {(r["company"], r["ncf"]) for r in cxc_rows}
    pdf_not_in_excel = []
    for inv in pdf_invoices:
        key = (inv.get("company"), norm_ncf(inv["ncf"]))
        if key not in excel_keys:
            # ncf might exist under same company only
            if not any(
                r["ncf"] == inv["ncf"] and r["company"] == inv.get("company")
                for r in cxc_rows
            ):
                pdf_not_in_excel.append(inv)

    return {
        "matched": matched,
        "missing_pdf": missing_pdf,
        "blocked": blocked,
        "pdf_not_in_excel": pdf_not_in_excel,
        "used": list(used),
    }
