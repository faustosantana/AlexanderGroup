# ruff: noqa
"""Read-only: every company document date must be DD/MM/YYYY."""

import re
from datetime import date

from odoo.addons.justech_alexander_reports.models.datefmt import dx_format_date

DMY = re.compile(r"^\d{2}/\d{2}/\d{4}$")
US = re.compile(r"^(0?[1-9]|1[0-2])/(3[01]|[12]\d|0?[1-9])/\d{4}$")


def _check(label, raw, formatted):
    expected = dx_format_date(raw) if raw else formatted
    ok = formatted == expected and (formatted == "—" or bool(DMY.match(formatted)))
    us_like = bool(formatted and US.match(formatted) and formatted != expected)
    print(
        "DATE",
        "PASS" if ok and not us_like else "FAIL",
        label,
        "raw",
        raw,
        "printed",
        formatted,
        "expected",
        expected,
    )
    return ok and not us_like


def run(env):
    sample = date(2027, 12, 31)
    helper = dx_format_date(sample)
    print("HELPER", helper, "env_lang", env.lang)
    if helper != "31/12/2027":
        raise SystemExit("HELPER_FAIL")

    langs = env["res.lang"].sudo().search([("active", "=", True)])
    lang_ok = True
    for lang in langs:
        print("LANG", lang.code, "date_format", lang.date_format)
        if lang.date_format != "%d/%m/%Y":
            lang_ok = False
            print("LANG_FAIL", lang.code)

    companies = env["res.company"].sudo().search([("dx_short_code", "!=", False)])
    codes = {c.dx_short_code: c for c in companies}
    failed = 0 if lang_ok else 1
    for code in ("BLU", "PIN", "DOM", "DOR", "MAY", "REM"):
        company = codes.get(code)
        if not company:
            print("COMPANY_MISSING", code)
            failed += 1
            continue
        ctx = {"allowed_company_ids": company.ids, "lang": "en_US"}
        Move = env["account.move"].sudo().with_company(company).with_context(**ctx)
        Sale = env["sale.order"].sudo().with_company(company).with_context(**ctx)
        PO = env["purchase.order"].sudo().with_company(company).with_context(**ctx)
        Pick = env["stock.picking"].sudo().with_company(company).with_context(**ctx)
        Pay = env["account.payment"].sudo().with_company(company).with_context(**ctx)
        inv = Move.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "in", ("out_invoice", "in_invoice", "out_refund")),
                ("state", "=", "posted"),
            ],
            order="id desc",
            limit=1,
        )
        if not inv:
            inv = Move.search(
                [
                    ("company_id", "=", company.id),
                    ("move_type", "in", ("out_invoice", "in_invoice", "out_refund")),
                ],
                order="id desc",
                limit=1,
            )
        if inv:
            dx = inv._dx_invoice_compose()
            meta = company._dx_header_meta_for(inv)
            if not _check(
                "%s invoice %s date" % (code, inv.name),
                inv.invoice_date or inv.date,
                dx.get("date"),
            ):
                failed += 1
            if dx.get("due") and not _check(
                "%s invoice %s due" % (code, inv.name),
                inv.invoice_date_due,
                dx.get("due"),
            ):
                failed += 1
            if dx.get("ncf_validity") and not _check(
                "%s invoice %s ncf" % (code, inv.name),
                inv._dx_invoice_ncf_validity_date(),
                dx.get("ncf_validity"),
            ):
                failed += 1
            if not _check(
                "%s invoice header %s" % (code, inv.name),
                inv.invoice_date or inv.date,
                meta.get("date"),
            ):
                failed += 1
        else:
            print("NO_INVOICE", code)
        sale = Sale.search([("company_id", "=", company.id)], order="id desc", limit=1)
        if sale:
            dx = sale._dx_sale_compose()
            if not _check(
                "%s sale %s" % (code, sale.name), sale.date_order, dx.get("date")
            ):
                failed += 1
        po = PO.search([("company_id", "=", company.id)], order="id desc", limit=1)
        if po:
            dx = po._dx_purchase_compose()
            if not _check("%s po %s" % (code, po.name), po.date_order, dx.get("date")):
                failed += 1
        pick = Pick.search([("company_id", "=", company.id)], order="id desc", limit=1)
        if pick:
            dx = pick._dx_picking_compose()
            if not _check(
                "%s picking %s" % (code, pick.name),
                pick.scheduled_date or pick.date_done,
                dx.get("date"),
            ):
                failed += 1
        pay = Pay.search([("company_id", "=", company.id)], order="id desc", limit=1)
        if pay:
            dx = pay._dx_payment_compose()
            if not _check("%s payment %s" % (code, pay.name), pay.date, dx.get("date")):
                failed += 1

    print("VERIFY_DATES", "PASS" if failed == 0 else "FAIL", "failed", failed)
    if failed:
        raise SystemExit(1)
    return True


run(env)
