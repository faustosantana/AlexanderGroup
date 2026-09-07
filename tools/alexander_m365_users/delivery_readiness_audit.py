# ruff: noqa
"""Auditoría de entrega: read-only + impresiones de documentos existentes.

No crea, no publica, no envía correo, no toca NCF. Rollback al final.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/tmp")
from catalog import (  # noqa: E402
    DEFAULT_COMPANY_ID,
    FORBIDDEN_SALES_ONLY_GROUPS,
    OPERATIONAL_COMPANY_IDS,
    PEOPLE,
)

OUT = os.environ.get("DELIVERY_AUDIT_OUT", "/tmp/delivery_readiness.json")
PDF_DIR = Path(os.environ.get("DELIVERY_PDF_DIR", "/tmp/delivery_prints"))
NCF_MARKERS = ("B1500000150", "B1500000110", "B1300000016")
EXPECTED_POSTED_OUT = 27
FAUSTO_LOGIN = "fausto@justech.do"


def _group_xmlids(user):
    names = set()
    for g in user.sudo().group_ids:
        xmlid = g.get_external_id().get(g.id)
        if xmlid:
            names.add(xmlid)
    return names


def _user_row(user):
    xmlids = _group_xmlids(user)
    return {
        "USER_ID": user.id,
        "LOGIN": user.login,
        "NAME": user.name,
        "ACTIVE": bool(user.active),
        "SHARE": bool(user.share),
        "DEFAULT_COMPANY_ID": user.company_id.id,
        "DEFAULT_COMPANY": user.company_id.name,
        "COMPANY_IDS": user.company_ids.ids,
        "SETTINGS": user.has_group("base.group_system"),
        "SALES": user.has_group("sales_team.group_sale_salesman_all_leads")
        or user.has_group("sales_team.group_sale_manager"),
        "PURCHASE": user.has_group("purchase.group_purchase_user")
        or user.has_group("purchase.group_purchase_manager"),
        "INVOICE": user.has_group("account.group_account_invoice"),
        "ACCT_ADMIN": user.has_group("account.group_account_manager"),
        "LOGIN_DATE": str(user.login_date) if user.login_date else None,
        "PARTNER_ID": user.partner_id.id,
    }


def _pick(env, model, domain, order="id desc"):
    return env[model].sudo().search(domain, order=order, limit=1)


def _render(env, xmlid, recs, label):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "label": label,
        "xmlid": xmlid,
        "doc": recs.display_name if recs else None,
        "id": recs.id if recs else None,
        "company": (
            recs.company_id.name if recs and "company_id" in recs._fields else None
        ),
    }
    if not recs:
        row["PRINT"] = "SKIP_NO_DOC"
        return row
    try:
        report = env.ref(xmlid)
        pdf, _typ = (
            report.sudo()
            .with_context(
                force_report_rendering=True,
                mail_notify_force_send=False,
            )
            ._render_qweb_pdf(report, res_ids=recs.ids)
        )
        name = "%s_%s.pdf" % (
            label,
            (recs.display_name or str(recs.id))
            .replace("/", "-")
            .replace(" ", "_")[:40],
        )
        dest = PDF_DIR / name
        dest.write_bytes(pdf)
        row.update(
            {
                "PRINT": "PASS" if pdf and pdf[:4] == b"%PDF" else "FAIL_NOT_PDF",
                "bytes": len(pdf),
                "file": str(dest),
            }
        )
    except Exception as exc:
        row.update(
            {"PRINT": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:240]}
        )
    return row


def main():
    Users = env["res.users"].with_context(active_test=False)
    report = {
        "mode": "READ_ONLY_PLUS_PRINT_ROLLBACK",
        "users": [],
        "fausto": {},
        "baseline": {},
        "prints": [],
        "guards": {},
    }

    for person in PEOPLE:
        user = Users.search([("login", "=", person["upn"])], limit=2)
        if len(user) != 1:
            report["users"].append(
                {
                    "PERSON": person["display_name"],
                    "LOGIN": person["upn"],
                    "STATUS": "MISSING" if not user else "DUPLICATE",
                    "IDS": user.ids,
                }
            )
            continue
        row = _user_row(user)
        row["PERSON"] = person["display_name"]
        row["EXPECTED_ADMIN"] = person["odoo_admin"]
        row["EXPECTED_INVOICE"] = person["invoicing"]
        xmlids = _group_xmlids(user)
        if person["key"] in ("luis", "janny", "elianny", "leopordo"):
            row["FORBIDDEN_HIT"] = sorted(xmlids & set(FORBIDDEN_SALES_ONLY_GROUPS))
        row["COMPANIES_OK"] = set(user.company_ids.ids) >= set(OPERATIONAL_COMPANY_IDS)
        row["DEFAULT_OK"] = user.company_id.id == DEFAULT_COMPANY_ID
        row["STATUS"] = "READY" if user.active and row["COMPANIES_OK"] else "BLOCK"
        report["users"].append(row)

    fausto = Users.search([("login", "=", FAUSTO_LOGIN)])
    if len(fausto) != 1:
        alt = Users.search(
            ["|", ("email", "=", FAUSTO_LOGIN), ("name", "ilike", "Fausto Santana")]
        )
        report["fausto"] = {
            "STATUS": "NOT_UNIQUE" if alt else "MISSING",
            "IDS": fausto.ids or alt.ids,
            "LOGINS": [u.login for u in (fausto or alt)],
        }
    else:
        row = _user_row(fausto)
        row["STATUS"] = "ACTIVE_READY" if fausto.active else "INACTIVE"
        row["CAN_ENTER"] = bool(fausto.active) and not fausto.share
        report["fausto"] = row

    Move = env["account.move"].sudo()
    posted_out = Move.search_count(
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("company_id", "in", list(OPERATIONAL_COMPANY_IDS)),
        ]
    )
    ncf_hits = {}
    for ncf in NCF_MARKERS:
        recs = (
            Move.search(
                [
                    "|",
                    ("justech_do_ncf", "=", ncf),
                    ("ref", "=", ncf),
                ]
            )
            if "justech_do_ncf" in Move._fields
            else Move.search([("ref", "=", ncf)])
        )
        ncf_hits[ncf] = {
            "count": len(recs),
            "ids": recs.ids,
            "states": recs.mapped("state"),
        }
    alex = Users.search([("login", "=", "alexander.pina@inversionesdoralex.com")])
    gmail = Users.search([("login", "=", "inversionesdoralex@gmail.com")])
    report["baseline"] = {
        "posted_out_invoices_ops": posted_out,
        "OPENING_INTACT": posted_out == EXPECTED_POSTED_OUT,
        "ncf_markers": ncf_hits,
        "NCF_MARKERS_PRESENT": all(v["count"] >= 1 for v in ncf_hits.values()),
        "superuser_id": 1,
        "superuser_login": Users.browse(1).login,
        "superuser_active": Users.browse(1).active,
        "alexander_uid": alex.id if len(alex) == 1 else alex.ids,
        "alexander_login_rows": len(alex),
        "old_gmail_login_rows": len(gmail),
        "attachment_count": env["ir.attachment"].sudo().search_count([]),
    }

    inv = _pick(
        env,
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("company_id", "=", DEFAULT_COMPANY_ID),
        ],
    )
    so = _pick(env, "sale.order", [("state", "in", ("draft", "sent", "sale"))])
    po = _pick(
        env, "purchase.order", [("state", "in", ("draft", "sent", "purchase", "done"))]
    )
    picking = _pick(
        env, "stock.picking", [("state", "in", ("done", "assigned", "confirmed"))]
    )
    pay = _pick(
        env,
        "account.payment",
        [("state", "in", ("posted", "in_process", "paid"))],
    )

    cr = env.cr
    cr.execute("SAVEPOINT delivery_print_audit")
    try:
        report["prints"].append(
            _render(env, "account.account_invoices", inv, "factura_cliente")
        )
        report["prints"].append(
            _render(env, "sale.action_report_saleorder", so, "cotizacion")
        )
        if report["prints"][-1].get("PRINT") == "FAIL":
            report["prints"].append(
                _render(env, "sale.report_saleorder", so, "cotizacion")
            )
        report["prints"].append(
            _render(env, "purchase.action_report_purchase_order", po, "orden_compra")
        )
        if report["prints"][-1].get("PRINT") == "FAIL":
            report["prints"].append(
                _render(env, "purchase.report_purchaseorder", po, "orden_compra")
            )
        report["prints"].append(
            _render(env, "stock.action_report_delivery", picking, "entrega")
        )
        report["prints"].append(
            _render(env, "account.action_report_payment_receipt", pay, "recibo")
        )
    finally:
        cr.execute("ROLLBACK TO SAVEPOINT delivery_print_audit")

    report["guards"] = {
        "posted_out_after": Move.search_count(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("company_id", "in", list(OPERATIONAL_COMPANY_IDS)),
            ]
        ),
        "attachment_count_after": env["ir.attachment"].sudo().search_count([]),
        "WRITES_LEFT": False,
    }
    report["guards"]["BASELINE_UNCHANGED"] = (
        report["guards"]["posted_out_after"] == posted_out
        and report["guards"]["attachment_count_after"]
        == report["baseline"]["attachment_count"]
    )
    prints_ok = all(p.get("PRINT") in ("PASS", "SKIP_NO_DOC") for p in report["prints"])
    users_ok = all(u.get("STATUS") == "READY" for u in report["users"])
    fausto_ok = report["fausto"].get("STATUS") == "ACTIVE_READY"
    report["DELIVERY_READY"] = bool(
        users_ok
        and fausto_ok
        and report["baseline"]["OPENING_INTACT"]
        and report["baseline"]["NCF_MARKERS_PRESENT"]
        and report["baseline"]["alexander_login_rows"] == 1
        and report["baseline"]["old_gmail_login_rows"] == 0
        and report["guards"]["BASELINE_UNCHANGED"]
        and prints_ok
    )
    env.cr.rollback()
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


main()
