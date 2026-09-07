# ruff: noqa
"""Auditoría read-only de readiness operativo. No escribe. No envía."""

import json
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BATCH = "ALEXANDER_OPENING_2026-09-04"
QA_START = 99100000
OUT = "/tmp/op_ready_audit.json"

EXCEL = {
    "132220112": {
        "name": "INVERSIONES DORALEX,S.RL.",
        "province": "SANTO DOMINGO",
        "start": "2020-11-02",
        "legal": "Alexander Piña Aquino",
        "legal_id": "223-0157134-9",
        "bank": "9604436830",
        "bank_bal": "5000000.00",
    },
    "132271068": {
        "name": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "province": "SANTO DOMINGO",
        "start": "2021-03-01",
        "legal": "Alba Rafaelina Arias Mora",
        "legal_id": "280-103907-0",
        "bank": "9604097492",
        "bank_bal": "2450000.00",
    },
    "132721502": {
        "name": "DOMINION BUSINESS,S.R.L.",
        "province": "DISTRITO NACIONAL",
        "start": "2022-11-09",
        "legal": "Arisleydi Contreras Suero",
        "legal_id": "402-4200332-1",
        "bank": "9605588726",
        "bank_bal": "1500000.00",
    },
    "132710152": {
        "name": "INVERSIONES EL MAYUMA, S.R.L.",
        "province": "SANTO DOMINGO",
        "start": "2022-09-14",
        "legal": "Eldris Marlenny Ramirez Minaya",
        "legal_id": "402-4218015-2",
        "bank": "9605543104",
        "bank_bal": "3000000.00",
    },
    "132769155": {
        "name": "REMPART GROUP S.R.L.",
        "province": "SANTO DOMINGO",
        "start": "2023-01-19",
        "legal": "Agustin Ventura Alcantara",
        "legal_id": "402-2314668-5",
        "bank": "9608739498",
        "bank_bal": "4600000.00",
    },
    "133371261": {
        "name": "BLUE ELITE, S.R.L.",
        "province": "SANTO DOMINGO",
        "start": "2025-04-04",
        "legal": "Geilin Rosario Suero",
        "legal_id": "402-1097505-4",
        "bank": "9608670542",
        "bank_bal": "1250000.00",
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
        "matrix": [],
        "ncf": [],
        "users": [],
        "qa_in_prod": [],
        "crons": [],
        "tech_company": {},
        "opening": {},
        "cross_company_leaks": [],
        "qweb": env["ir.ui.view"].search_count(
            [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
        ),
        "ecf": env["ir.config_parameter"]
        .sudo()
        .get_param("justech_alexander.ecf_operational_enabled"),
        "enterprise": {},
    }

    # opening baseline
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
            missing.append(m.justech_do_ncf)
    bills = env["account.move"].search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "in_invoice"),
        ]
    )
    report["opening"] = {
        "count": len(opening),
        "ar_total": str(ar),
        "pdfs": pdfs,
        "missing_pdf": missing,
        "vendor_bills_opening": len(bills),
        "unbalanced": sum(
            1
            for m in opening
            if abs(sum(m.line_ids.mapped("debit")) - sum(m.line_ids.mapped("credit")))
            > 0.005
        ),
        "0150": next(
            (
                {
                    "total": float(m.amount_total),
                    "residual": float(m.amount_residual),
                }
                for m in opening
                if m.justech_do_ncf == "B1500000150"
            ),
            None,
        ),
        "rempart_110": next(
            (
                {
                    "total": float(m.amount_total),
                    "residual": float(m.amount_residual),
                    "company": m.company_id.name,
                }
                for m in opening
                if m.justech_do_ncf == "B1500000110"
                and "REMPART" in (m.company_id.name or "").upper()
            ),
            None,
        ),
    }

    # technical company
    tech_moves = env["account.move"].search_count([("company_id", "=", 1)])
    tech_journals = env["account.journal"].search_count([("company_id", "=", 1)])
    tech_wh = (
        env["stock.warehouse"].search_count([("company_id", "=", 1)])
        if "stock.warehouse" in env
        else 0
    )
    users_on_tech = env["res.users"].search(
        [("company_ids", "in", [1]), ("share", "=", False)]
    )
    report["tech_company"] = {
        "id": 1,
        "name": tech.name,
        "currency": tech.currency_id.name,
        "country": tech.country_id.code,
        "active": tech.active,
        "moves": tech_moves,
        "journals": tech_journals,
        "warehouses": tech_wh,
        "users_with_access": [
            {"login": u.login, "default": u.company_id.id} for u in users_on_tech
        ],
        "TECHNICAL_COMPANY_SAFE_TO_ARCHIVE": "NO",
        "reason": (
            "Usuarios internos aún la tienen en company_ids; es plantilla US/USD. "
            "Archivarla ahora puede romper properties/multi-company. No eliminar."
        ),
    }

    # users
    for u in env["res.users"].search([("share", "=", False)], order="id"):
        gnames = set(u.group_ids.mapped("name") if "group_ids" in u._fields else [])
        if not gnames:
            gnames = set(u.groups_id.mapped("name"))
        report["users"].append(
            {
                "id": u.id,
                "login": u.login,
                "name": u.name,
                "active": u.active,
                "default_company": u.company_id.name,
                "allowed": u.company_ids.mapped("name"),
                "admin": "Settings" in gnames
                or any("Administration" in n for n in gnames)
                or u.has_group("base.group_system"),
                "sales": u.has_group("sales_team.group_sale_salesman"),
                "purchase": u.has_group("purchase.group_purchase_user"),
                "accounting": u.has_group("account.group_account_invoice"),
                "inventory": u.has_group("stock.group_stock_user"),
                "portal": u.has_group("base.group_portal"),
            }
        )

    # NCF
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
            seqs = []
            for m in hist:
                n = m.justech_do_ncf or ""
                if len(n) == 11 and n[3:].isdigit() and int(n[3:]) < QA_START:
                    seqs.append(int(n[3:]))
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

    # per company
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
        taxes = e["account.tax"].search(
            [
                ("company_id", "=", c.id),
                ("type_tax_use", "=", "sale"),
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
        for j in bank_j:
            acc_code = (
                getattr(j, "default_account_id", False) and j.default_account_id.code
            )
            number = ""
            if j.bank_account_id:
                number = j.bank_account_id.acc_number or ""
            bank_accs.append(
                {
                    "journal": j.name,
                    "code": j.code,
                    "number": number,
                    "currency": j.currency_id.name or c.currency_id.name,
                    "gl": acc_code,
                    "inbound": bool(j.inbound_payment_method_line_ids),
                    "outbound": bool(j.outbound_payment_method_line_ids),
                }
            )
        # bank GL balance
        posted_bank = Decimal("0")
        opening_bank_exists = False
        for j in bank_j:
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
        ar_co = sum(
            (_money(m.amount_residual) for m in opening if m.company_id.id == c.id),
            Decimal("0"),
        )
        ap_art = e["account.move"].search_count(
            [
                ("company_id", "=", c.id),
                ("move_type", "=", "in_invoice"),
                ("invoice_origin", "=", BATCH),
            ]
        )
        logo = bool(c.logo)
        start = ""
        if "l10n_do_dgii_start_date" in c._fields:
            start = str(c.l10n_do_dgii_start_date or "")
        ncf_active = [
            n
            for n in report["ncf"]
            if n["company"] == c.name and n["status"] == "SAFE_ACTIVE"
        ]
        leak_ctx = env["account.move"].with_context(allowed_company_ids=[c.id])
        foreign = leak_ctx.search(
            [
                ("move_type", "in", ("out_invoice", "in_invoice")),
                ("state", "=", "posted"),
                ("company_id", "!=", c.id),
            ]
        )
        report["cross_company_leaks"].append(
            {
                "viewer_company": c.name,
                "foreign_moves": len(foreign),
                "sample": [
                    {"id": m.id, "company": m.company_id.name, "ncf": m.justech_do_ncf}
                    for m in foreign[:5]
                ],
            }
        )

        def row(area, item, current, expected, status, action, risk="LOW"):
            report["matrix"].append(
                {
                    "COMPANY": c.name,
                    "AREA": area,
                    "ITEM": item,
                    "CURRENT_VALUE": current,
                    "EXPECTED_VALUE": expected,
                    "SOURCE": "Excel Levantamiento / prod",
                    "STATUS": status,
                    "ACTION_REQUIRED": action,
                    "RISK": risk,
                }
            )

        row(
            "LEGAL",
            "RNC",
            vat,
            src.get("rnc"),
            "READY" if vat == src.get("rnc") else "PARTIAL",
            "none" if vat == src.get("rnc") else "review RNC",
        )
        row(
            "LEGAL",
            "state_id",
            p.state_id.name if p.state_id else "",
            src.get("province"),
            "MISSING" if not p.state_id else "READY",
            "map provincia Excel" if not p.state_id else "none",
        )
        row(
            "LEGAL",
            "fecha_inicio",
            start,
            src.get("start"),
            "MISSING" if not start else "READY",
            "map l10n_do_dgii_start_date" if not start else "none",
        )
        row(
            "LEGAL",
            "representante",
            getattr(c, "dx_legal_representative", "") or "",
            src.get("legal"),
            "READY" if (getattr(c, "dx_legal_representative", "") or "") else "MISSING",
            "none",
        )
        row(
            "BANK",
            "banreservas_number",
            ",".join(b["number"] for b in bank_accs),
            src.get("bank"),
            (
                "READY"
                if src.get("bank")
                and any(src["bank"] in (b["number"] or "") for b in bank_accs)
                else "PARTIAL"
            ),
            "do not change account number",
        )
        row(
            "BANK",
            "opening_balance_posted",
            str(posted_bank),
            src.get("bank_bal"),
            "NEEDS_BUSINESS_CONFIRMATION",
            "Excel date 05//08/2026 invalid; do not post until valid date",
            "HIGH",
        )
        row(
            "NCF",
            "safe_active_ranges",
            str(len(ncf_active)),
            "only evidenced ranges",
            "PARTIAL" if ncf_active else "BLOCKED",
            "keep blocked ranges blocked",
        )
        row(
            "INV",
            "warehouse",
            ",".join(wh.mapped("name")),
            "Oficina principal / warehouse",
            "READY" if wh else "MISSING",
            "none" if wh else "ensure warehouse exists",
        )
        row(
            "ACC",
            "sale_journal",
            str(len(sale_j)),
            ">=1",
            "READY" if sale_j else "MISSING",
            "none",
        )
        row(
            "ACC",
            "purchase_journal",
            str(len(purch_j)),
            ">=1",
            "READY" if purch_j else "MISSING",
            "none",
        )
        row(
            "ACC",
            "itbis_18",
            str(len(taxes)),
            ">=1",
            "READY" if taxes else "MISSING",
            "none",
        )
        row(
            "BRAND",
            "logo",
            "yes" if logo else "no",
            "yes",
            "READY" if logo else "MISSING",
            "none" if logo else "confirm logo asset",
        )

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
                "logo": logo,
                "sale_journals": sale_j.mapped("name"),
                "purchase_journals": purch_j.mapped("name"),
                "bank_journals": bank_accs,
                "posted_bank_gl": str(posted_bank),
                "opening_bank_entry": opening_bank_exists,
                "excel_bank_balance": src.get("bank_bal"),
                "excel_bank_date": "05//08/2026",
                "itbis18": taxes.mapped("name"),
                "warehouses": wh.mapped("name"),
                "receivable_accounts": len(rec_acc),
                "payable_accounts": len(pay_acc),
                "opening_ar": str(ar_co),
                "artificial_ap": ap_art,
                "ncf_safe_active": ncf_active,
            }
        )

    # QA leftovers in prod
    Partner = env["res.partner"]
    for rec in Partner.search(
        [
            "|",
            "|",
            ("name", "ilike", "DXQA"),
            ("name", "ilike", "DX TEST"),
            ("vat", "ilike", "9910"),
        ]
    ):
        report["qa_in_prod"].append(
            {
                "model": "res.partner",
                "id": rec.id,
                "name": rec.name,
                "company": rec.company_id.name,
            }
        )
    for rec in env["product.product"].search(
        ["|", ("name", "ilike", "DXQA"), ("default_code", "ilike", "DXQA")]
    ):
        report["qa_in_prod"].append(
            {
                "model": "product.product",
                "id": rec.id,
                "name": rec.name,
            }
        )
    for rec in env["account.move"].search(
        [
            "|",
            "|",
            ("name", "ilike", "DXQA"),
            ("ref", "ilike", "DXQA"),
            ("justech_do_ncf", "=like", "B019910%"),
        ]
    ):
        report["qa_in_prod"].append(
            {
                "model": "account.move",
                "id": rec.id,
                "name": rec.name,
                "ncf": rec.justech_do_ncf,
                "company": rec.company_id.name,
                "state": rec.state,
            }
        )

    # crons
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

    # enterprise
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

    mail_sent = env["mail.mail"].search_count(
        [("create_date", ">=", "2026-09-04"), ("state", "in", ("sent", "outgoing"))]
    )
    report["mail_sent_since_opening"] = mail_sent
    report["CROSS_COMPANY_DATA_LEAK"] = sum(
        r["foreign_moves"] for r in report["cross_company_leaks"]
    )

    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print("WROTE", OUT)
    print(
        json.dumps(
            {
                "opening": report["opening"],
                "qweb": report["qweb"],
                "ecf": report["ecf"],
                "CROSS_COMPANY_DATA_LEAK": report["CROSS_COMPANY_DATA_LEAK"],
                "users": len(report["users"]),
                "ncf": len(report["ncf"]),
                "qa": len(report["qa_in_prod"]),
                "crons": len(report["crons"]),
                "enterprise": report["enterprise"],
                "tech": report["tech_company"]["TECHNICAL_COMPANY_SAFE_TO_ARCHIVE"],
            },
            indent=2,
            default=str,
        )
    )


if "env" in globals():
    run(env)
