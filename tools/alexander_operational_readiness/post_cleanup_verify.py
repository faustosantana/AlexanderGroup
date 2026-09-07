# ruff: noqa
"""Verificación post-limpieza. Read-only."""

import json
from decimal import Decimal
from pathlib import Path

BATCH = "ALEXANDER_OPENING_2026-09-04"
OUT = "/tmp/op_ready_post_cleanup.json"


def _money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def run(env):
    opening = env["account.move"].search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
    )
    ar = sum((_money(m.amount_residual) for m in opening), Decimal("0"))
    qa_active_partners = env["res.partner"].search(
        [
            "|",
            ("name", "ilike", "DX TEST"),
            ("name", "ilike", "NO FISCAL REAL"),
        ]
    )
    qa_posted = env["account.move"].search(
        [
            ("state", "=", "posted"),
            "|",
            ("justech_do_ncf", "=like", "%9910%"),
            ("partner_id.name", "ilike", "DX TEST"),
        ]
    )
    qa_users = env["res.users"].search(
        ["|", ("login", "ilike", "dx.test"), ("name", "ilike", "DX TEST")]
    )
    ncf = []
    for r in env["justech.do.ncf.range"].search(
        [
            ("company_id", "!=", 1),
            ("state", "=", "active"),
            ("sequence_start", "<", 99100000),
        ]
    ):
        ncf.append(
            {
                "company": r.company_id.name,
                "prefix": r.prefix,
                "next": r.next_ncf_display,
                "auth": r.authorization_number,
            }
        )
    emails = [
        {"company": c.name, "email": c.email}
        for c in env["res.company"].search([("id", "!=", 1)], order="id")
    ]
    stock = []
    for c in env["res.company"].search([("id", "!=", 1)]):
        qs = env["stock.quant"].search(
            [("company_id", "=", c.id), ("quantity", "!=", 0)]
        )
        stock.append(
            {
                "company": c.name,
                "nonzero": len(qs),
                "qty": float(sum(qs.mapped("quantity"))),
            }
        )
    out = {
        "opening_count": len(opening),
        "ar": str(ar),
        "0150": next(
            (
                float(m.amount_total)
                for m in opening
                if m.justech_do_ncf == "B1500000150"
            ),
            None,
        ),
        "rempart_110": next(
            (
                float(m.amount_total)
                for m in opening
                if m.justech_do_ncf == "B1500000110"
                and "REMPART" in (m.company_id.name or "").upper()
            ),
            None,
        ),
        "b13_pdf": next(
            (
                env["ir.attachment"].search_count(
                    [
                        ("res_model", "=", "account.move"),
                        ("res_id", "=", m.id),
                        ("mimetype", "=", "application/pdf"),
                    ]
                )
                for m in opening
                if m.justech_do_ncf == "B1300000016"
            ),
            None,
        ),
        "pdfs": sum(
            1
            for m in opening
            if env["ir.attachment"].search_count(
                [
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", m.id),
                    ("mimetype", "=", "application/pdf"),
                ]
            )
        ),
        "qweb": env["ir.ui.view"].search_count(
            [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
        ),
        "ecf": env["ir.config_parameter"]
        .sudo()
        .get_param("justech_alexander.ecf_operational_enabled"),
        "mail": env["mail.mail"].search_count(
            [
                ("create_date", ">=", "2026-09-07"),
                ("state", "in", ("sent", "outgoing")),
            ]
        ),
        "qa_active_partners": [p.name for p in qa_active_partners],
        "qa_posted_moves": len(qa_posted),
        "qa_active_users": [u.login for u in qa_users],
        "ncf_active": ncf,
        "emails": emails,
        "stock": stock,
    }
    Path(OUT).write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
