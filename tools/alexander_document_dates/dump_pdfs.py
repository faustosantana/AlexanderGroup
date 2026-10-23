# ruff: noqa
"""Write sample PDFs to /tmp. Does not post or change NCF."""

import os

OUT = "/tmp/dx_dmy_pdfs"
os.makedirs(OUT, exist_ok=True)

samples = [
    ("account.move", "account.account_invoices", "out_invoice", "invoice"),
    ("sale.order", "sale.action_report_saleorder", None, "sale"),
    ("purchase.order", "purchase.action_report_purchaseorder", None, "purchase"),
    ("stock.picking", "stock.action_report_delivery", None, "picking"),
    ("account.payment", "account.action_report_payment_receipt", None, "payment"),
]


def _latest(env, model, company, move_type=None):
    Model = env[model].sudo()
    domain = [("company_id", "=", company.id)]
    if move_type:
        domain += [("move_type", "=", move_type), ("state", "=", "posted")]
    rec = Model.search(domain, order="id desc", limit=1)
    return rec


def run(env):
    Report = env["ir.actions.report"].sudo()
    companies = env["res.company"].sudo().search([("dx_short_code", "!=", False)])
    written = 0
    for company in companies:
        code = company.dx_short_code
        for model, xmlid, move_type, kind in samples:
            rec = _latest(env, model, company, move_type)
            if not rec:
                print("DUMP_SKIP", code, kind)
                continue
            action = xmlid
            try:
                pdf, _ext = Report.with_company(company)._render_qweb_pdf(
                    action, rec.ids
                )
            except Exception as exc:
                print("DUMP_ERR", code, kind, rec.display_name, type(exc).__name__)
                continue
            name = "%s_%s_%s.pdf" % (
                code,
                kind,
                (rec.name or rec.display_name or str(rec.id)).replace("/", "-"),
            )
            path = os.path.join(OUT, name)
            with open(path, "wb") as handle:
                handle.write(pdf)
            print("DUMP", path, "bytes", len(pdf))
            written += 1
    # Explicit previously-US invoice
    inv = (
        env["account.move"]
        .sudo()
        .search([("name", "=", "INV/2026/00025"), ("company_id.dx_short_code", "=", "DOR")], limit=1)
    )
    if inv:
        pdf, _ext = Report.with_company(inv.company_id)._render_qweb_pdf(
            "account.account_invoices", inv.ids
        )
        path = os.path.join(OUT, "DOR_invoice_INV-2026-00025.pdf")
        with open(path, "wb") as handle:
            handle.write(pdf)
        print("DUMP", path, "bytes", len(pdf))
        written += 1
    print("DUMP_DONE", written)
    return True


run(env)
