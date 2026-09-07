# ruff: noqa
"""Renderiza PDF de cotización/OC en staging. No envía correo."""

import base64
import json
from pathlib import Path

TAG = "DXQA-OPREADY-20260907"
OUT_DIR = Path("/tmp/op_ready_reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run(env):
    report = {"pdfs": [], "MAIL_SENT": 0}
    Report = env["ir.actions.report"]
    for so in env["sale.order"].search([("client_order_ref", "=", TAG)]):
        try:
            pdf, _ = Report._render_qweb_pdf("sale.report_saleorder", so.ids)
            dest = (
                OUT_DIR
                / f"{so.company_id.dx_short_code or so.company_id.id}_{so.name.replace('/', '-')}_so.pdf"
            )
            dest.write_bytes(pdf)
            report["pdfs"].append(
                {
                    "company": so.company_id.name,
                    "doc": so.name,
                    "bytes": len(pdf),
                    "file": dest.name,
                }
            )
        except Exception as exc:
            report["pdfs"].append(
                {"company": so.company_id.name, "doc": so.name, "error": str(exc)}
            )
    for po in env["purchase.order"].search([("partner_ref", "=", TAG)]):
        try:
            pdf, _ = Report._render_qweb_pdf("purchase.report_purchaseorder", po.ids)
            dest = (
                OUT_DIR
                / f"{po.company_id.dx_short_code or po.company_id.id}_{po.name.replace('/', '-')}_po.pdf"
            )
            dest.write_bytes(pdf)
            report["pdfs"].append(
                {
                    "company": po.company_id.name,
                    "doc": po.name,
                    "bytes": len(pdf),
                    "file": dest.name,
                }
            )
        except Exception as exc:
            report["pdfs"].append(
                {"company": po.company_id.name, "doc": po.name, "error": str(exc)}
            )
    Path("/tmp/op_ready_reports.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if "env" in globals():
    run(env)
