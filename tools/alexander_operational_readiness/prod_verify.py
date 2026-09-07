# ruff: noqa
"""Re-verificación read-only post-fix. No escribe. No envía."""

import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BATCH = "ALEXANDER_OPENING_2026-09-04"
QA_START = 99100000
OUT = "/tmp/op_ready_verify.json"

EXCEL = {
    "132220112": {
        "name": "INVERSIONES DORALEX,S.RL.",
        "trade": "Doralex",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "start": "2020-11-02",
        "legal": "Alexander Piña Aquino",
        "legal_id": "223-0157134-9",
        "bank": "9604436830",
        "bank_bal": "5000000.00",
        "phone": "849-207-5817",
        "email_excel": "inversionesdoralex@gmail.com",
    },
    "132271068": {
        "name": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "trade": "Piñaria",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "start": "2021-03-01",
        "legal": "Alba Rafaelina Arias Mora",
        "legal_id": "280-103907-0",
        "bank": "9604097492",
        "bank_bal": "2450000.00",
        "phone": "849-207-5817",
        "email_excel": "piñariascomercializadora@gmail.com",
    },
    "132721502": {
        "name": "DOMINION BUSINESS,S.R.L.",
        "trade": "Dominion",
        "province": "DISTRITO NACIONAL",
        "municipality": "DISTRITO NACIONAL",
        "start": "2022-11-09",
        "legal": "Arisleydi Contreras Suero",
        "legal_id": "402-4200332-1",
        "bank": "9605588726",
        "bank_bal": "1500000.00",
        "phone": "829-941-5257",
        "email_excel": "dominionsrl@hotmail.com",
    },
    "132710152": {
        "name": "INVERSIONES EL MAYUMA, S.R.L.",
        "trade": "El Mayuma",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "start": "2022-09-14",
        "legal": "Eldris Marlenny Ramirez Minaya",
        "legal_id": "402-4218015-2",
        "bank": "9605543104",
        "bank_bal": "3000000.00",
        "phone": "829-696-1881",
        "email_excel": "inversioneselmayuma@gmail.com",
    },
    "132769155": {
        "name": "REMPART GROUP S.R.L.",
        "trade": "Rempart",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "start": "2023-01-19",
        "legal": "Agustin Ventura Alcantara",
        "legal_id": "402-2314668-5",
        "bank": "9608739498",
        "bank_bal": "4600000.00",
        "phone": "849-394-1927",
        "email_excel": "rempartsrl@hotmail.com",
    },
    "133371261": {
        "name": "BLUE ELITE, S.R.L.",
        "trade": "Blue Elite",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "start": "2025-04-04",
        "legal": "Geilin Rosario Suero",
        "legal_id": "402-1097505-4",
        "bank": "9608670542",
        "bank_bal": "1250000.00",
        "phone": "809-614-1306",
        "email_excel": "bluelitesrl@hotmail.com",
    },
}


def _vat(s):
    return re.sub(r"\D", "", str(s or ""))


def _money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def run(env):
    Company = env["res.company"].sudo()
    ops = Company.search([("id", "!=", 1)], order="id")
    tech = Company.browse(1)
    report = {
        "database": env.cr.dbname,
        "companies": [],
        "ncf": [],
        "users": [],
        "qa": {"partners": [], "products": [], "moves": [], "users": []},
        "crons": [],
        "tech_company": {},
        "opening": {},
        "leaks": {},
        "email": [],
        "products_opening": {},
        "qweb": env["ir.ui.view"].search_count(
            [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
        ),
        "ecf": env["ir.config_parameter"]
        .sudo()
        .get_param("justech_alexander.ecf_operational_enabled"),
        "enterprise": {},
        "mail": {},
        "b1300000016": {},
    }

    opening = env["account.move"].search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
    )
    ar = sum((_money(m.amount_residual) for m in opening), Decimal("0"))
    pdfs = 0
    missing = []
    by_co = defaultdict(lambda: Decimal("0"))
    for m in opening:
        atts = env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", m.id),
                ("mimetype", "=", "application/pdf"),
            ]
        )
        if atts:
            pdfs += 1
        else:
            missing.append(
                {
                    "ncf": m.justech_do_ncf,
                    "id": m.id,
                    "name": m.name,
                    "company": m.company_id.name,
                }
            )
        by_co[m.company_id.name] += _money(m.amount_residual)

    bills = env["account.move"].search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "in_invoice"),
        ]
    )
    inv0150 = next((m for m in opening if m.justech_do_ncf == "B1500000150"), None)
    rem110 = next(
        (
            m
            for m in opening
            if m.justech_do_ncf == "B1500000110"
            and "REMPART" in (m.company_id.name or "").upper()
        ),
        None,
    )
    b13 = next((m for m in opening if m.justech_do_ncf == "B1300000016"), None)
    report["opening"] = {
        "count": len(opening),
        "ar_total": str(ar),
        "ar_by_company": {k: str(v) for k, v in by_co.items()},
        "pdfs": pdfs,
        "missing_pdf": missing,
        "vendor_bills_opening": len(bills),
        "unbalanced": sum(
            1
            for m in opening
            if abs(sum(m.line_ids.mapped("debit")) - sum(m.line_ids.mapped("credit")))
            > 0.005
        ),
        "0150": (
            {
                "id": inv0150.id,
                "name": inv0150.name,
                "total": float(inv0150.amount_total),
                "residual": float(inv0150.amount_residual),
            }
            if inv0150
            else None
        ),
        "rempart_110": (
            {
                "id": rem110.id,
                "name": rem110.name,
                "total": float(rem110.amount_total),
                "residual": float(rem110.amount_residual),
                "company": rem110.company_id.name,
            }
            if rem110
            else None
        ),
    }
    if b13:
        atts = env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", b13.id),
                ("mimetype", "=", "application/pdf"),
            ]
        )
        report["b1300000016"] = {
            "id": b13.id,
            "name": b13.name,
            "company": b13.company_id.name,
            "total": float(b13.amount_total),
            "residual": float(b13.amount_residual),
            "pdf_count": len(atts),
            "SOURCE_DOCUMENT_STATUS": "MISSING_PDF" if not atts else "HAS_PDF",
            "narration": (b13.narration or "")[:200],
        }

    report["tech_company"] = {
        "id": 1,
        "name": tech.name,
        "currency": tech.currency_id.name,
        "country": tech.country_id.code,
        "active": tech.active,
        "moves": env["account.move"].search_count([("company_id", "=", 1)]),
        "journals": env["account.journal"].search_count([("company_id", "=", 1)]),
        "warehouses": (
            env["stock.warehouse"].search_count([("company_id", "=", 1)])
            if "stock.warehouse" in env
            else 0
        ),
        "users_with_access": [
            {"login": u.login, "default": u.company_id.id}
            for u in env["res.users"].search(
                [("company_ids", "in", [1]), ("share", "=", False)]
            )
        ],
        "TECHNICAL_COMPANY_SAFE_TO_ARCHIVE": "NO",
    }

    for u in env["res.users"].search([("share", "=", False)], order="id"):
        report["users"].append(
            {
                "id": u.id,
                "login": u.login,
                "name": u.name,
                "active": u.active,
                "default_company": u.company_id.name,
                "allowed": u.company_ids.mapped("name"),
                "allowed_ids": u.company_ids.ids,
                "admin": u.has_group("base.group_system"),
                "sales": u.has_group("sales_team.group_sale_salesman"),
                "purchase": u.has_group("purchase.group_purchase_user"),
                "accounting": u.has_group("account.group_account_invoice"),
                "inventory": u.has_group("stock.group_stock_user"),
                "portal": u.has_group("base.group_portal"),
            }
        )

    if "justech.do.ncf.range" in env:
        for r in env["justech.do.ncf.range"].search([("company_id", "!=", 1)]):
            hist = env["account.move"].search(
                [
                    ("company_id", "=", r.company_id.id),
                    ("justech_do_ncf", "=like", f"{r.prefix}%"),
                    ("state", "=", "posted"),
                    ("move_type", "=", "out_invoice"),
                ]
            )
            max_hist = None
            for m in hist:
                n = m.justech_do_ncf or ""
                if len(n) == 11 and n[3:].isdigit() and int(n[3:]) < QA_START:
                    if max_hist is None or int(n[3:]) > int(max_hist[3:]):
                        max_hist = n
            qa = r.sequence_start >= QA_START
            if qa:
                status = "QA_CANCELLED" if r.state == "cancelled" else "QA_STILL_ACTIVE"
            elif r.state == "active" and r.sequence_start < QA_START:
                status = "SAFE_ACTIVE"
            elif r.state != "active":
                status = "NOT_USED" if not max_hist else "HISTORICAL_ONLY"
            else:
                status = "BLOCKED_CONFLICT"
            report["ncf"].append(
                {
                    "company": r.company_id.name,
                    "company_id": r.company_id.id,
                    "ncf_type": r.prefix,
                    "from": r.sequence_start,
                    "to": r.sequence_end,
                    "next": r.next_sequence,
                    "next_ncf": r.next_ncf_display,
                    "state": r.state,
                    "auth": r.authorization_number,
                    "max_historical": max_hist,
                    "status": status,
                    "qa": qa,
                }
            )

    restricted = env["res.users"].browse(7)
    if restricted.exists():
        env_u = env(user=restricted.id)
        seen = env_u["account.move"].search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice")),
                ("state", "=", "posted"),
            ]
        )
        foreign = seen.filtered(lambda m: m.company_id.id != 8)
        report["leaks"]["restricted_user"] = {
            "login": restricted.login,
            "active": restricted.active,
            "allowed": restricted.company_ids.ids,
            "seen": len(seen),
            "foreign": len(foreign),
        }
    alex = env["res.users"].search(
        [("login", "=", "inversionesdoralex@gmail.com")], limit=1
    )
    if alex:
        env_a = env(user=alex.id, context={"allowed_company_ids": [11]})
        seen = env_a["account.move"].search(
            [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
        )
        foreign = seen.filtered(lambda m: m.company_id.id != 11)
        report["leaks"]["alexander_doralex_only"] = {
            "seen": len(seen),
            "foreign": len(foreign),
        }
        report["leaks"]["alexander_allowed"] = alex.company_ids.ids
        report["leaks"]["alexander_default"] = alex.company_id.id

    Account = env["account.account"]
    for c in ops:
        vat = _vat(c.vat or c.partner_id.vat)
        src = EXCEL.get(vat, {})
        p = c.partner_id
        e = env(context=dict(env.context, allowed_company_ids=[c.id]))
        sale_j = e["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "sale")]
        )
        bank_j = e["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "bank")]
        )
        purch_j = e["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "purchase")]
        )
        cash_j = e["account.journal"].search(
            [("company_id", "=", c.id), ("type", "=", "cash")]
        )
        taxes = e["account.tax"].search(
            [
                ("company_id", "=", c.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 18),
            ]
        )
        purch_taxes = e["account.tax"].search(
            [
                ("company_id", "=", c.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 18),
            ]
        )
        wh = (
            e["stock.warehouse"].search([("company_id", "=", c.id)])
            if "stock.warehouse" in e
            else e["stock.warehouse"]
        )
        rec_acc = Account.search([("account_type", "=", "asset_receivable")]).filtered(
            lambda a, cid=c.id: not a.company_ids or cid in a.company_ids.ids
        )
        pay_acc = Account.search([("account_type", "=", "liability_payable")]).filtered(
            lambda a, cid=c.id: not a.company_ids or cid in a.company_ids.ids
        )
        bank_accs = []
        posted_bank = Decimal("0")
        opening_bank_exists = False
        for j in bank_j:
            acc_code = (
                getattr(j, "default_account_id", False) and j.default_account_id.code
            )
            number = j.bank_account_id.acc_number if j.bank_account_id else ""
            bank_accs.append(
                {
                    "journal": j.name,
                    "code": j.code,
                    "number": number,
                    "currency": j.currency_id.name or c.currency_id.name,
                    "gl": acc_code,
                    "inbound": bool(j.inbound_payment_method_line_ids),
                    "outbound": bool(j.outbound_payment_method_line_ids),
                    "outstanding_receipts": [
                        l.payment_account_id.code
                        for l in j.inbound_payment_method_line_ids
                        if l.payment_account_id
                    ],
                    "outstanding_payments": [
                        l.payment_account_id.code
                        for l in j.outbound_payment_method_line_ids
                        if l.payment_account_id
                    ],
                }
            )
            if j.default_account_id:
                lines = e["account.move.line"].search(
                    [
                        ("account_id", "=", j.default_account_id.id),
                        ("parent_state", "=", "posted"),
                    ]
                )
                posted_bank += _money(sum(lines.mapped("balance")))
                if any(
                    "apertura" in (ml.move_id.ref or "").lower()
                    or "opening" in (ml.move_id.ref or "").lower()
                    or "saldo inicial" in (ml.name or "").lower()
                    for ml in lines
                ):
                    opening_bank_exists = True
        qty = Decimal("0")
        if "stock.quant" in e:
            quants = e["stock.quant"].search([("company_id", "=", c.id)])
            qty = _money(sum(quants.mapped("quantity")))
        start = ""
        if "l10n_do_dgii_start_date" in c._fields:
            start = str(c.l10n_do_dgii_start_date or "")
        ncf_active = [
            n
            for n in report["ncf"]
            if n["company"] == c.name and n["status"] == "SAFE_ACTIVE"
        ]
        catchall = ""
        if "catchall_email" in c._fields:
            catchall = c.catchall_email or ""
        report["companies"].append(
            {
                "id": c.id,
                "name": c.name,
                "vat": vat,
                "email": c.email or p.email,
                "phone": c.phone or p.phone,
                "street": p.street,
                "city": p.city,
                "state": p.state_id.name if p.state_id else "",
                "country": p.country_id.code,
                "currency": c.currency_id.name,
                "legal": getattr(c, "dx_legal_representative", "") or "",
                "legal_id": getattr(c, "dx_legal_id_number", "") or "",
                "trade": getattr(c, "dx_trade_name", "") or "",
                "start": start,
                "logo": bool(c.logo),
                "sale_journals": sale_j.mapped("name"),
                "purchase_journals": purch_j.mapped("name"),
                "cash_journals": cash_j.mapped("name"),
                "bank_journals": bank_accs,
                "posted_bank_gl": str(posted_bank),
                "opening_bank_entry": opening_bank_exists,
                "excel_bank": src.get("bank"),
                "excel_bank_balance": src.get("bank_bal"),
                "excel_bank_date": "05//08/2026",
                "itbis18_sale": taxes.mapped("name"),
                "itbis18_purchase": purch_taxes.mapped("name"),
                "warehouses": wh.mapped("name"),
                "receivable_accounts": rec_acc.mapped("code")[:8],
                "payable_accounts": pay_acc.mapped("code")[:8],
                "opening_ar": str(by_co.get(c.name, Decimal("0"))),
                "artificial_ap": e["account.move"].search_count(
                    [
                        ("company_id", "=", c.id),
                        ("move_type", "=", "in_invoice"),
                        ("invoice_origin", "=", BATCH),
                    ]
                ),
                "ncf_safe_active": ncf_active,
                "stock_qty": str(qty),
                "excel": src,
                "catchall": catchall,
            }
        )
        report["email"].append(
            {
                "company": c.name,
                "odoo_email": c.email or p.email,
                "excel_email": src.get("email_excel"),
                "catchall": catchall,
            }
        )

    Partner = env["res.partner"]
    for rec in Partner.search(
        [
            "|",
            "|",
            "|",
            ("name", "ilike", "DXQA"),
            ("name", "ilike", "DX TEST"),
            ("name", "ilike", "DXQA-OPREADY"),
            ("vat", "ilike", "9910"),
        ]
    ):
        report["qa"]["partners"].append(
            {"id": rec.id, "name": rec.name, "company": rec.company_id.name}
        )
    for rec in env["product.product"].search(
        ["|", ("name", "ilike", "DXQA"), ("default_code", "ilike", "DXQA")]
    ):
        report["qa"]["products"].append({"id": rec.id, "name": rec.name})
    qa_moves = env["account.move"].search(
        [
            "|",
            ("justech_do_ncf", "=like", "%9910%"),
            ("partner_id.name", "ilike", "DX TEST"),
        ]
    )
    qa_residual = Decimal("0")
    for rec in qa_moves:
        qa_residual += _money(rec.amount_residual)
        report["qa"]["moves"].append(
            {
                "id": rec.id,
                "name": rec.name,
                "ncf": rec.justech_do_ncf,
                "company": rec.company_id.name,
                "state": rec.state,
                "total": float(rec.amount_total),
                "residual": float(rec.amount_residual),
                "origin": rec.invoice_origin,
            }
        )
    report["qa"]["residual_sum"] = str(qa_residual)
    for u in env["res.users"].search(
        ["|", ("login", "ilike", "dx.test"), ("name", "ilike", "DX TEST")]
    ):
        report["qa"]["users"].append({"id": u.id, "login": u.login, "active": u.active})

    opening_products = env["product.product"].search(
        [("create_date", ">=", "2026-09-04"), ("create_date", "<", "2026-09-06")]
    )
    report["products_opening"] = {
        "created_around_opening_window": len(opening_products),
        "sale_ok": sum(1 for p in opening_products if p.sale_ok),
        "purchase_ok": sum(1 for p in opening_products if p.purchase_ok),
        "types": {},
    }
    types = defaultdict(int)
    for p in opening_products:
        types[p.type] += 1
    report["products_opening"]["types"] = dict(types)

    for cron in env["ir.cron"].sudo().search([("active", "=", True)]):
        name = cron.name or ""
        code = (cron.code or "") if "code" in cron._fields else ""
        risky = any(
            k in (name + code).lower()
            for k in ("ecf", "dgii", "607", "606", "608", "enviar", "transmit")
        )
        report["crons"].append(
            {
                "id": cron.id,
                "name": name,
                "model": cron.model_id.model if cron.model_id else "",
                "interval": f"{cron.interval_number} {cron.interval_type}",
                "risky_name": risky,
            }
        )

    mod = env["ir.module.module"].search([("name", "=", "web_enterprise")], limit=1)
    reports = env["ir.module.module"].search(
        [("name", "=", "justech_alexander_reports")], limit=1
    )
    report["enterprise"] = {
        "web_enterprise": mod.state if mod else "missing",
        "web_enterprise_version": mod.latest_version if mod else "",
        "alexander_reports": reports.latest_version if reports else "",
        "db_uuid": env["ir.config_parameter"].sudo().get_param("database.uuid"),
        "expiration": env["ir.config_parameter"]
        .sudo()
        .get_param("database.expiration_date"),
    }
    report["mail"] = {
        "sent_or_outgoing_since_opening": env["mail.mail"].search_count(
            [
                ("create_date", ">=", "2026-09-04"),
                ("state", "in", ("sent", "outgoing")),
            ]
        ),
        "mail_server_count": env["ir.mail_server"].search_count([]),
        "mail_servers": [
            {"id": s.id, "name": s.name, "from_filter": getattr(s, "from_filter", "")}
            for s in env["ir.mail_server"].search([])
        ],
    }

    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print("WROTE", OUT)
    print(
        json.dumps(
            {
                "opening": report["opening"],
                "b13": report["b1300000016"],
                "qweb": report["qweb"],
                "ecf": report["ecf"],
                "leaks": report["leaks"],
                "users": len(report["users"]),
                "ncf_safe": sum(
                    1 for n in report["ncf"] if n["status"] == "SAFE_ACTIVE"
                ),
                "ncf_total": len(report["ncf"]),
                "qa_moves": len(report["qa"]["moves"]),
                "qa_residual": report["qa"]["residual_sum"],
                "crons": len(report["crons"]),
                "risky_crons": sum(1 for c in report["crons"] if c["risky_name"]),
                "enterprise": report["enterprise"],
                "mail": report["mail"]["sent_or_outgoing_since_opening"],
                "tech": report["tech_company"]["TECHNICAL_COMPANY_SAFE_TO_ARCHIVE"],
                "companies": [
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "state": c["state"],
                        "start": c["start"],
                        "bank": [b["number"] for b in c["bank_journals"]],
                        "posted_bank": c["posted_bank_gl"],
                        "logo": c["logo"],
                        "ncf_safe": len(c["ncf_safe_active"]),
                    }
                    for c in report["companies"]
                ],
            },
            indent=2,
            default=str,
        )
    )


if "env" in globals():
    run(env)
