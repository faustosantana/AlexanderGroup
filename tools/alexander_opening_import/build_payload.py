#!/usr/bin/env python3
"""Construye el payload de importación (Excel + PDFs). No toca Odoo."""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.alexander_opening_import.b001_catalog import B001_INVOICES
from tools.alexander_opening_import.match import match_invoices
from tools.alexander_opening_import.normalize import money, ncf_prefix, ncf_seq
from tools.alexander_opening_import.parse_excel import parse_workbook
from tools.alexander_opening_import.scan_catalog import SCAN_INVOICES
from tools.alexander_opening_import.split_pdfs import split_source_pdfs


def _dec(v):
    return str(money(v))


def build(excel_path: Path, pdf_paths: list[Path], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    excel = parse_workbook(excel_path)
    split = split_source_pdfs(pdf_paths, out_dir / "split_pages")
    pdf_invoices = list(SCAN_INVOICES) + list(B001_INVOICES)
    matched = match_invoices(excel["cxc"], pdf_invoices)

    # max NCF per company/type from excel+pdf
    max_ncf = {}
    for row in excel["cxc"]:
        key = (row["company"], ncf_prefix(row["ncf"]))
        seq = ncf_seq(row["ncf"])
        if seq is None:
            continue
        prev = max_ncf.get(key)
        if prev is None or seq > prev[0]:
            max_ncf[key] = (seq, row["ncf"])

    ncf_report = []
    for seq in excel["ncf_sequences"]:
        key = (seq["company"], seq["declared_type"])
        mx = max_ncf.get(key)
        extra = []
        if mx and seq["next"] and ncf_seq(seq["next"]) is not None:
            if mx[0] >= ncf_seq(seq["next"]):
                extra.append(f"DOCS_GE_DECLARED_NEXT max={mx[1]} next={seq['next']}")
        rec = dict(seq)
        rec["max_doc_ncf"] = mx[1] if mx else None
        rec["conflicts"] = list(seq["conflicts"]) + extra
        rec["status"] = "NCF_SEQUENCE_CONFLICT" if rec["conflicts"] else "CONSISTENT"
        ncf_report.append(rec)

    ar = {}
    for row in excel["cxc"]:
        ar.setdefault(row["company"], Decimal("0"))
        ar[row["company"]] += money(row["amount_residual"])

    payload = {
        "batch": f"ALEXANDER_OPENING_{date.today().isoformat()}",
        "excel": excel_path.name,
        "cutover": excel["cutover"],
        "users_to_create": len(excel["users"]),
        "vendor_bills_to_import": len(excel["cxp"]),
        "fixed_assets_to_import": len(excel["fixed_assets"]),
        "customers_master_real": len(excel["customers_master"]),
        "cxc": excel["cxc"],
        "cxp": excel["cxp"],
        "ncf_sequences": ncf_report,
        "match": {
            "matched": matched["matched"],
            "missing_pdf": matched["missing_pdf"],
            "blocked": matched["blocked"],
            "pdf_not_in_excel": matched["pdf_not_in_excel"],
        },
        "excel_ar_totals": {k: str(v) for k, v in ar.items()},
        "split": [
            {
                "SOURCE_FILE": s["SOURCE_FILE"],
                "pages": s["pages"],
                "sha256": s["sha256"],
            }
            for s in split
        ],
        "pdf_files": [p.name for p in pdf_paths],
        "pdf_pages": sum(s["pages"] for s in split),
    }
    (out_dir / "payload.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return payload


def main():
    uploads = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
    excel = uploads / "Plantilla_PENDIENTES_Alexander_Odoo_1e80.xlsx"
    pdfs = [
        uploads / "DORALEX-CXC-FACT-B15_cc82.pdf",
        uploads / "DORALEX-CXC-FACT-B001_a53b.pdf",
        uploads / "MAYUMA-CXC-FACT-B15_1e65.pdf",
        uploads / "REMPART-CXC-FACT-B15_f167.pdf",
    ]
    out = Path("/tmp/alexander_opening_payload")
    payload = build(excel, pdfs, out)
    m = payload["match"]
    print("USERS_TO_CREATE", payload["users_to_create"])
    print("VENDOR_BILLS_TO_IMPORT", payload["vendor_bills_to_import"])
    print("FIXED_ASSETS_TO_IMPORT", payload["fixed_assets_to_import"])
    print("EXCEL_CXC_ROWS", len(payload["cxc"]))
    print("MATCHED", len(m["matched"]))
    print("MISSING_PDF", [r["ncf"] for r in m["missing_pdf"]])
    print("BLOCKED", [(r["ncf"], r.get("match_reasons")) for r in m["blocked"]])
    print(
        "PDF_NOT_IN_EXCEL",
        [(i.get("company"), i["ncf"]) for i in m["pdf_not_in_excel"]],
    )
    print(
        "NCF_CONFLICTS",
        sum(1 for s in payload["ncf_sequences"] if s["status"] != "CONSISTENT"),
    )
    print("AR", payload["excel_ar_totals"])
    print("wrote", out / "payload.json")


if __name__ == "__main__":
    main()
