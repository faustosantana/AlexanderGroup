"""Extractor de facturas desde texto (pdftotext -layout) y OCR débil."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .normalize import money, norm_ncf, norm_vat, parse_money_in_text

NCF_FIND = re.compile(r"\b([BE]\d{2}\d{8})\b", re.I)
DATE_FIND = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
LINE_START = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+([A-Za-zÁÉÍÓÚÑ°³/]+)\s+"
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2}))"
)


def pdftotext_layout(path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.stdout or ""


def parse_date_dmy(text: str) -> str | None:
    m = DATE_FIND.search(text.replace("FECHA:", " FECHA:"))
    if not m:
        return None
    raw = m.group(1).replace("-", "/")
    parts = raw.split("/")
    if len(parts) != 3:
        return None
    d, mo, y = parts
    if len(y) == 2:
        y = "20" + y
    try:
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    except ValueError:
        return None


def _line_amount(text: str) -> str | None:
    dollars = re.findall(r"\$\s*([\d.,]+)", text)
    if dollars:
        return str(money(dollars[-1]))
    return None


def extract_lines_from_text(page_text: str) -> list[dict]:
    lines = []
    body = False
    for raw in page_text.splitlines():
        if re.search(r"COD\.?\s+DESCRIPCION", raw, re.I):
            body = True
            continue
        if re.search(r"SUB\s*TOTAL|ITBIS|TOTAL IMPORTE|FIRMA AUTORIZADA", raw, re.I):
            body = False
        if not body:
            continue
        if re.search(r"^\s*Nota", raw, re.I):
            continue
        m = re.match(
            r"^\s*(\d+(?:\.\d+)?)\s+(.+)$",
            raw,
        )
        if not m:
            continue
        rest = m.group(2).strip()
        amount = _line_amount(rest)
        qty = None
        uom = None
        price = None
        qty_m = re.search(
            r"(\d+(?:[.,]\d+)?)\s+([A-Za-zÁÉÍÓÚÑ³0-9/]+)\s+(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2}))",
            rest,
        )
        desc = rest
        if qty_m:
            qty = str(money(qty_m.group(1)))
            uom = qty_m.group(2)
            price = str(money(qty_m.group(3)))
            desc = rest[: qty_m.start()].strip()
        desc = re.sub(r"\$\s*[\d.,]+", "", desc).strip(" -")
        if not desc or len(desc) < 3:
            continue
        if amount is None and price and qty:
            try:
                amount = str(money(float(qty) * float(price)))
            except Exception:
                amount = price
        if amount is None:
            continue
        lines.append(
            {
                "description": desc,
                "qty": qty or "1",
                "uom": uom or "UND",
                "price_unit": price or amount,
                "line_total": amount,
            }
        )
    return lines


def extract_invoice_from_text(
    page_text: str, source_file: str, page: int
) -> dict | None:
    ncfs = [norm_ncf(m.group(1)) for m in NCF_FIND.finditer(page_text)]
    if not ncfs:
        return None
    # issuer NCF is typically the last / rightmost in header
    ncf = ncfs[-1]
    vat_candidates = re.findall(
        r"\b(\d{3}[-–]\d{5}[-–]\d|\d{1}-\d{2}-\d{5}-\d)\b", page_text
    )
    customer = None
    cm = re.search(r"CLIENTE:\s*(.+?)(?:\s{2,}RNC:|\s{2,}NCF:|$)", page_text)
    if cm:
        customer = cm.group(1).strip()
    totals = {}
    for raw in page_text.splitlines():
        if re.search(r"SUB\s*TOTAL", raw, re.I):
            totals["subtotal"] = str(parse_money_in_text(raw) or "")
        if re.search(r"ITBIS", raw, re.I):
            if re.search(r"EXCENTO|EXENTO", raw, re.I):
                totals["itbis"] = "0.00"
                totals["tax_exempt"] = True
            else:
                amt = parse_money_in_text(raw)
                if amt is not None:
                    totals["itbis"] = str(amt)
        if re.search(r"TOTAL IMPORTE|TOTAL\s*$", raw, re.I) or (
            raw.strip().startswith("$") and "totals" in totals
        ):
            amt = parse_money_in_text(raw)
            if amt is not None:
                totals["total"] = str(amt)
    # last money after EXCENTO often is total
    if "total" not in totals:
        last = None
        for raw in page_text.splitlines():
            if "$" in raw or "RD$" in raw:
                last = parse_money_in_text(raw)
        if last is not None:
            totals["total"] = str(last)
    refs = []
    for pat in (
        r"No\.?\s*orden:\s*(\S+)",
        r"REFERENCIA:\s*(\S+)",
        r"CONTRATO[^:]*:\s*(\S+)",
        r"(PROPEEP[-A-Z0-9/]+)",
        r"(ASDE[-A-Z0-9]+)",
        r"(TRABAJO[-A-Z0-9]+)",
    ):
        for m in re.finditer(pat, page_text, re.I):
            refs.append(m.group(1).strip())
    issuer_vat = ""
    if vat_candidates:
        issuer_vat = norm_vat(vat_candidates[0])
    customer_vat = ""
    rnc_line = re.search(r"RNC:\s*([0-9\-]+)", page_text)
    if rnc_line:
        customer_vat = norm_vat(rnc_line.group(1))
    return {
        "ncf": ncf,
        "customer": customer,
        "customer_vat": customer_vat,
        "issuer_vat": issuer_vat,
        "invoice_date": parse_date_dmy(page_text),
        "subtotal": totals.get("subtotal"),
        "itbis": totals.get("itbis"),
        "tax_exempt": bool(totals.get("tax_exempt")),
        "total": totals.get("total"),
        "references": refs,
        "lines": extract_lines_from_text(page_text),
        "source_file": source_file,
        "source_page": page,
        "extract_method": "pdftotext",
    }


def extract_text_pdf(path: Path) -> list[dict]:
    text = pdftotext_layout(path)
    pages = text.split("\f")
    found = []
    for i, page in enumerate(pages, start=1):
        if not page.strip():
            continue
        inv = extract_invoice_from_text(page, path.name, i)
        if inv:
            found.append(inv)
    return found
