# ruff: noqa
"""Importador ORM de apertura Alexander. Ejecutar dentro de odoo shell.
Lee OPENING_PAYLOAD_JSON. No SQL de insert. No e-CF. No mail. No stock.
"""

import base64
import json
import os
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

PAYLOAD_PATH = os.environ.get("OPENING_PAYLOAD_JSON", "/tmp/opening_payload.json")
PDF_DIR = os.environ.get("OPENING_PDF_DIR", "/tmp/alexander_opening_pdfs")
BATCH = os.environ.get("OPENING_BATCH", "ALEXANDER_OPENING_2026-09-04")
DRY = os.environ.get("OPENING_DRY_RUN", "0") == "1"

REPORT = {
    "CUSTOMERS_CREATED": 0,
    "CUSTOMERS_REUSED": 0,
    "CUSTOMER_DUPLICATES_CREATED": 0,
    "VENDORS_CREATED": 0,
    "VENDORS_REUSED": 0,
    "PRODUCTS_CREATED": 0,
    "PRODUCTS_REUSED": 0,
    "PRODUCT_DUPLICATES_CREATED": 0,
    "CUSTOMER_INVOICES_CREATED": 0,
    "CUSTOMER_INVOICES_EXISTING": 0,
    "CUSTOMER_INVOICES_BLOCKED": 0,
    "VENDOR_BILLS_CREATED": 0,
    "VENDOR_BILLS_EXISTING": 0,
    "VENDOR_BILLS_BLOCKED": 0,
    "HISTORICAL_PAYMENTS_WITH_EVIDENCE": 0,
    "MIGRATION_PAYMENT_APPLICATIONS": 0,
    "UNBALANCED_IMPORTED_MOVES": 0,
    "NCF_CONSUMED": 0,
    "MAIL_SENT": 0,
    "ECF_SENT": 0,
    "DGII_SENT": 0,
    "WEBSITE_TOUCHED": False,
    "errors": [],
    "blocked": [],
    "created_moves": [],
    "products": [],
    "clearing_accounts": {},
}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().upper()


def _vat(s):
    return re.sub(r"\D", "", str(s or ""))


def _money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ctx():
    return {
        "mail_create_nosubscribe": True,
        "mail_notrack": True,
        "tracking_disable": True,
        "no_reset_password": True,
        "tracking_disable_one": True,
    }


def load_payload():
    return json.loads(Path(PAYLOAD_PATH).read_text(encoding="utf-8"))


COMPANY_VAT = {
    "INVERSIONES DORALEX,S.RL.": "132220112",
    "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.": "132271068",
    "DOMINION BUSINESS,S.R.L.": "132721502",
    "INVERSIONES EL MAYUMA, S.R.L.": "132710152",
    "REMPART GROUP S.R.L.": "132769155",
    "BLUE ELITE, S.R.L.": "133371261",
}

COMPANY_CODE = {
    "INVERSIONES DORALEX,S.RL.": "DORALEX",
    "INVERSIONES EL MAYUMA, S.R.L.": "MAYUMA",
    "REMPART GROUP S.R.L.": "REMPART",
}


def find_company(env, name):
    vat = COMPANY_VAT.get(name)
    Company = env["res.company"]
    if vat:
        rec = Company.search(
            [
                (
                    "vat",
                    "in",
                    [
                        vat,
                        (
                            vat[:3] + "-" + vat[3:8] + "-" + vat[8:]
                            if len(vat) == 9
                            else vat
                        ),
                    ],
                )
            ],
            limit=1,
        )
        if rec:
            return rec
        for c in Company.search([("id", "!=", 1)]):
            if _vat(c.vat) == vat or _vat(c.partner_id.vat) == vat:
                return c
    rec = Company.search([("name", "=", name)], limit=1)
    if rec:
        return rec
    for c in Company.search([]):
        if _norm(c.name).startswith(_norm(name)[:18]):
            return c
    return Company.browse()


def find_sale_journal(env, company):
    Journal = env["account.journal"].with_company(company)
    j = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
    )
    return j


def find_misc_journal(env, company):
    Journal = env["account.journal"].with_company(company)
    j = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "general")],
        limit=1,
        order="id",
    )
    return j


def find_clearing_account(env, company):
    Account = env["account.account"].with_company(company)
    domain_company = [
        "|",
        ("company_ids", "in", [company.id]),
        ("company_ids", "=", False),
    ]
    for term in ("migracion", "migración", "apertura", "transitoria", "opening"):
        acc = Account.search(domain_company + [("name", "ilike", term)], limit=1)
        if acc:
            return acc
    # otras cuentas por cobrar / diversas
    acc = Account.search(domain_company + [("name", "ilike", "divers")], limit=5)
    for a in acc:
        if "cobrar" in (a.name or "").lower() or "receiv" in (a.name or "").lower():
            return a
    acc = Account.search(
        domain_company
        + [("account_type", "=", "asset_current"), ("name", "ilike", "otra")],
        limit=1,
    )
    return acc


def find_itbis_tax(env, company):
    Tax = env["account.tax"].with_company(company)
    taxes = Tax.search(
        [
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 18),
            "|",
            ("company_id", "=", company.id),
            ("company_ids", "in", [company.id]),
        ]
    )
    if not taxes:
        taxes = Tax.search([("type_tax_use", "=", "sale"), ("amount", "=", 18)])
    # prefer non-withholding
    for t in taxes:
        name = (t.name or "").lower()
        if "reten" in name or "withhold" in name:
            continue
        return t
    return taxes[:1]


def find_doc_type(env, prefix):
    Doc = env["justech.do.fiscal.document.type"]
    rec = Doc.search([("prefix", "=", prefix)], limit=1)
    return rec


def find_or_create_partner(env, company, name, vat, doc_type):
    Partner = env["res.partner"].with_context(**_ctx())
    vat_n = _vat(vat)
    existing = Partner.search([("vat", "!=", False)])
    hits = existing.filtered(lambda p: _vat(p.vat) == vat_n)
    if hits:
        partner = hits.sorted(lambda p: (p.company_id.id or 0))[0]
        REPORT["CUSTOMERS_REUSED"] += 1
        vals = {}
        if "justech_do_fiscal_config_state" in partner._fields:
            if partner.justech_do_fiscal_config_state in (
                False,
                "pending_new",
                "needs_review",
            ):
                vals["justech_do_fiscal_config_state"] = "confirmed_history"
        if doc_type and "justech_do_default_document_type_id" in partner._fields:
            if not partner.justech_do_default_document_type_id:
                vals["justech_do_default_document_type_id"] = doc_type.id
        if vals:
            partner.with_context(**_ctx()).write(vals)
        return partner
    vals = {
        "name": name,
        "vat": vat_n,
        "customer_rank": 1,
        "company_id": False,
        "country_id": env.ref("base.do").id,
    }
    if "justech_do_fiscal_config_state" in Partner._fields:
        vals["justech_do_fiscal_config_state"] = "confirmed_history"
    if "justech_do_fiscal_config_source" in Partner._fields:
        vals["justech_do_fiscal_config_source"] = BATCH
    if doc_type and "justech_do_default_document_type_id" in Partner._fields:
        vals["justech_do_default_document_type_id"] = doc_type.id
    if "l10n_do_dgii_tax_payer_type" in Partner._fields:
        vals["l10n_do_dgii_tax_payer_type"] = "taxpayer"
    partner = Partner.create(vals)
    REPORT["CUSTOMERS_CREATED"] += 1
    return partner


def find_or_create_product(env, company, desc, uom_name, is_service, price):
    Product = env["product.product"].with_company(company).with_context(**_ctx())
    Template = env["product.template"].with_company(company).with_context(**_ctx())
    key = _norm(desc)
    cands = Product.search([("name", "ilike", desc[:40])])
    for p in cands:
        if _norm(p.name) == key:
            REPORT["PRODUCTS_REUSED"] += 1
            REPORT["products"].append(
                {"id": p.id, "name": p.name, "status": "REUSED", "source": desc}
            )
            return p
    # broader
    allp = Product.search([])
    for p in allp:
        if _norm(p.name) == key:
            REPORT["PRODUCTS_REUSED"] += 1
            REPORT["products"].append(
                {"id": p.id, "name": p.name, "status": "REUSED", "source": desc}
            )
            return p
    uom = find_uom(env, uom_name)
    tvals = {
        "name": desc[:128],
        "type": "service" if is_service else "consu",
        "sale_ok": True,
        "purchase_ok": False,
        "list_price": float(price or 0),
        "company_id": False,
        "invoice_policy": "order",
    }
    if "is_storable" in Template._fields:
        tvals["is_storable"] = False
    if uom and "uom_id" in Template._fields:
        tvals["uom_id"] = uom.id
        if "uom_po_id" in Template._fields:
            tvals["uom_po_id"] = uom.id
    tmpl = Template.create(tvals)
    product = tmpl.product_variant_id
    REPORT["PRODUCTS_CREATED"] += 1
    REPORT["products"].append(
        {
            "id": product.id,
            "name": product.name,
            "status": "CREATED",
            "type": tvals["type"],
            "source": desc,
        }
    )
    return product


def find_uom(env, name):
    Uom = env["uom.uom"]
    mapping = {
        "Units": ["Units", "Unit", "Unidad", "UND", "Ud"],
        "m3": ["m³", "m3", "m3"],
        "Resma": ["Resma"],
        "Funda": ["Funda", "FDA"],
        "Galon": ["Galon", "Galón", "Gallon", "GL"],
        "Cubeta": ["Cubeta", "CUB"],
        "Rollo": ["Rollo"],
        "Pie": ["Pie", "Foot", "ft"],
        "Days": ["Days", "Day", "Días", "Dias"],
        "lb": ["lb", "lbs", "Pound"],
    }
    targets = mapping.get(name, [name, "Units"])
    for t in targets:
        rec = Uom.search([("name", "=", t)], limit=1)
        if rec:
            return rec
        rec = Uom.search([("name", "ilike", t)], limit=1)
        if rec:
            return rec
    return Uom.search([("name", "in", ["Units", "Unit", "Unidades"])], limit=1)


def existing_move(env, company, ncf):
    Move = env["account.move"].with_company(company)
    domain = [
        ("company_id", "=", company.id),
        ("move_type", "=", "out_invoice"),
        ("justech_do_ncf", "=", ncf),
    ]
    rec = Move.search(domain, limit=2)
    if rec:
        return rec
    if "l10n_latam_document_number" in Move._fields:
        rec = Move.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "=", "out_invoice"),
                ("l10n_latam_document_number", "=", ncf),
            ],
            limit=2,
        )
    return rec


def is_service(desc):
    d = _norm(desc)
    return any(
        x in d
        for x in (
            "SERVICIO",
            "TRANSPORTE",
            "CORTE",
            "CARGA",
            "BOTE ",
            "GESTION",
            "DIRECCION TECNICA",
            "PEAJE",
            "COMBUSTIBLE",
            "CAJA CHICA",
            "TRASLADO",
            "REGADO",
            "RAMPA",
            "DT ",
        )
    )


def attach_pdf(env, move, company_name, ncf, source_file, source_page):
    code = COMPANY_CODE.get(company_name, "CO")
    # prefer renamed individual
    candidates = [
        Path(PDF_DIR) / f"{code}_{ncf}.pdf",
        Path(PDF_DIR) / f"{source_file}",
    ]
    data = None
    fname = f"{code}_{ncf}.pdf"
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            data = c.read_bytes()
            break
    if data is None:
        # page split
        stem = Path(source_file).stem
        page = source_page or 1
        for c in Path(PDF_DIR).glob(f"{stem}*_page_{int(page):02d}.pdf"):
            data = c.read_bytes()
            break
        if data is None:
            for c in Path(PDF_DIR).glob(f"*{ncf}*.pdf"):
                data = c.read_bytes()
                break
    if not data:
        return False
    env["ir.attachment"].with_context(**_ctx()).create(
        {
            "name": fname,
            "res_model": "account.move",
            "res_id": move.id,
            "type": "binary",
            "datas": base64.b64encode(data),
            "mimetype": "application/pdf",
            "description": json.dumps(
                {
                    "SOURCE_FILE": source_file,
                    "SOURCE_PAGE": source_page,
                    "migration_batch": BATCH,
                }
            ),
        }
    )
    return True


def apply_migration_residual(env, company, move, paid_amount, partner):
    paid = _money(paid_amount)
    if paid <= 0:
        return False
    clearing = find_clearing_account(env, company)
    journal = find_misc_journal(env, company)
    if not clearing or not journal:
        REPORT["errors"].append(
            {
                "ncf": move.justech_do_ncf,
                "error": "NO_CLEARING_OR_MISC_JOURNAL",
                "clearing": bool(clearing),
                "journal": bool(journal),
            }
        )
        return False
    REPORT["clearing_accounts"][company.name] = {
        "account": (
            f"{clearing.code} {clearing.name}"
            if hasattr(clearing, "code")
            else clearing.display_name
        ),
        "journal": journal.name,
    }
    recv = move.line_ids.filtered(
        lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
    )
    if not recv:
        return False
    Move = env["account.move"].with_company(company).with_context(**_ctx())
    entry = Move.create(
        {
            "move_type": "entry",
            "company_id": company.id,
            "journal_id": journal.id,
            "date": move.invoice_date,
            "ref": f"{BATCH} PAY {move.justech_do_ncf}",
            "invoice_origin": BATCH,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "account_id": recv[0].account_id.id,
                        "partner_id": partner.id,
                        "name": f"Apertura histórica aplicada {move.justech_do_ncf}",
                        "credit": float(paid),
                    },
                ),
                (
                    0,
                    0,
                    {
                        "account_id": clearing.id,
                        "partner_id": partner.id,
                        "name": f"Clearing apertura {move.justech_do_ncf}",
                        "debit": float(paid),
                    },
                ),
            ],
        }
    )
    entry.action_post()
    counterpart = entry.line_ids.filtered(lambda l: l.account_id == recv[0].account_id)
    (recv + counterpart).reconcile()
    REPORT["MIGRATION_PAYMENT_APPLICATIONS"] += 1
    return True


def import_one(env, row):
    company = find_company(env, row["company"])
    if not company:
        REPORT["CUSTOMER_INVOICES_BLOCKED"] += 1
        REPORT["blocked"].append({**row, "reason": "COMPANY_NOT_FOUND"})
        return
    ncf = row["ncf"]
    existing = existing_move(env, company, ncf)
    if existing:
        REPORT["CUSTOMER_INVOICES_EXISTING"] += 1
        return existing[0]
    pdf = row.get("pdf") or {}
    if not row.get("balance_ok", True):
        REPORT["CUSTOMER_INVOICES_BLOCKED"] += 1
        REPORT["blocked"].append({**row, "reason": "EXCEL_BALANCE_EQUATION"})
        return
    prefix = ncf[:3]
    doc = find_doc_type(env, prefix)
    partner = find_or_create_partner(
        env, company, row.get("customer") or pdf.get("customer"), row.get("vat"), doc
    )
    journal = find_sale_journal(env, company)
    if not journal:
        REPORT["CUSTOMER_INVOICES_BLOCKED"] += 1
        REPORT["blocked"].append({**row, "reason": "NO_SALE_JOURNAL"})
        return
    tax = None
    exempt = bool(pdf.get("tax_exempt"))
    if not exempt:
        tax = find_itbis_tax(env, company)
    lines_src = pdf.get("lines") or []
    if not lines_src:
        lines_src = [
            {
                "description": f"Apertura histórica {ncf} (sin desglose PDF)",
                "qty": "1",
                "uom": "UND",
                "price_unit": row["amount_original"],
                "line_total": row["amount_original"],
            }
        ]
    invoice_lines = []
    for ln in lines_src:
        product = find_or_create_product(
            env,
            company,
            ln["description"],
            # uom already canon in payload? map raw
            {
                "M3": "m3",
                "RESMA": "Resma",
                "FDA": "Funda",
                "GL": "Galon",
                "CUBETA": "Cubeta",
                "CUB": "Cubeta",
                "ROLLO": "Rollo",
                "PIE": "Pie",
                "DIAS": "Days",
                "LB": "lb",
                "UND": "Units",
                "UD": "Units",
                "PA": "Units",
                "KIT": "Units",
            }.get(str(ln.get("uom") or "UND").upper().replace(".", ""), "Units"),
            is_service(ln["description"]),
            _money(ln.get("price_unit")),
        )
        lvals = {
            "product_id": product.id,
            "name": ln["description"],
            "quantity": float(_money(ln.get("qty") or 1)),
            "price_unit": float(_money(ln.get("price_unit"))),
        }
        if tax and not exempt:
            lvals["tax_ids"] = [(6, 0, tax.ids)]
        else:
            lvals["tax_ids"] = [(6, 0, [])]
        invoice_lines.append((0, 0, lvals))
    Move = env["account.move"].with_company(company).with_context(**_ctx())
    refs = pdf.get("references") or []
    vals = {
        "move_type": "out_invoice",
        "company_id": company.id,
        "partner_id": partner.id,
        "journal_id": journal.id,
        "invoice_date": row["invoice_date"],
        "invoice_line_ids": invoice_lines,
        "ref": ncf,
        "invoice_origin": BATCH,
        "payment_reference": " ".join(refs)[:128] if refs else ncf,
        "narration": f"{BATCH} SOURCE_FILE={pdf.get('source_file')} SOURCE_PAGE={pdf.get('source_page')}",
    }
    if "justech_do_ncf" in Move._fields:
        vals["justech_do_ncf"] = ncf
    if "l10n_latam_document_number" in Move._fields:
        vals["l10n_latam_document_number"] = ncf
    if doc and "justech_do_document_type_id" in Move._fields:
        vals["justech_do_document_type_id"] = doc.id
    if DRY:
        REPORT["created_moves"].append(
            {"dry": True, "ncf": ncf, "company": company.name}
        )
        return
    ncf_before = []
    if "justech.do.ncf.range" in env:
        ncf_before = (
            env["justech.do.ncf.range"]
            .search([("company_id", "=", company.id)])
            .mapped(
                lambda r: (
                    r.id,
                    getattr(r, "next_sequence", None)
                    or getattr(r, "sequence_next", None),
                )
            )
        )
    move = Move.create(vals)
    move.with_context(**_ctx()).action_post()
    if "justech.do.ncf.range" in env:
        ncf_after = (
            env["justech.do.ncf.range"]
            .search([("company_id", "=", company.id)])
            .mapped(
                lambda r: (
                    r.id,
                    getattr(r, "next_sequence", None)
                    or getattr(r, "sequence_next", None),
                )
            )
        )
        if ncf_after != ncf_before:
            REPORT["NCF_CONSUMED"] += 1
            REPORT["errors"].append({"ncf": ncf, "error": "SEQUENCE_CONSUMED"})
    posted = move.line_ids.filtered(lambda l: l.display_type == "product" or True)
    debit = sum(move.line_ids.mapped("debit"))
    credit = sum(move.line_ids.mapped("credit"))
    if abs(debit - credit) > 0.005:
        REPORT["UNBALANCED_IMPORTED_MOVES"] += 1
    excel_total = _money(row["amount_original"])
    if abs(_money(move.amount_total) - excel_total) > Decimal("0.05"):
        REPORT["errors"].append(
            {
                "ncf": ncf,
                "error": "POSTED_TOTAL_NE_EXCEL",
                "odoo": float(move.amount_total),
                "excel": float(excel_total),
            }
        )
    paid = _money(row.get("amount_paid") or 0)
    if paid > 0:
        apply_migration_residual(env, company, move, paid, partner)
    attached = attach_pdf(
        env,
        move,
        row["company"],
        ncf,
        pdf.get("source_file") or "",
        pdf.get("source_page"),
    )
    REPORT["CUSTOMER_INVOICES_CREATED"] += 1
    REPORT["created_moves"].append(
        {
            "id": move.id,
            "ncf": ncf,
            "company": company.name,
            "partner": partner.name,
            "total": float(move.amount_total),
            "residual": float(move.amount_residual),
            "payment_state": move.payment_state,
            "attached": attached,
            "unbalanced": abs(debit - credit) > 0.005,
        }
    )
    return move


def run(env):
    payload = load_payload()
    env = env(context={**env.context, **_ctx()})
    to_import = payload["match"]["matched"]
    # missing PDF with complete excel fields: import after matched
    for row in payload["match"]["missing_pdf"]:
        if (
            row.get("ncf")
            and row.get("vat")
            and row.get("invoice_date")
            and row.get("amount_original")
        ):
            row = dict(row)
            row["pdf"] = {
                "lines": [],
                "tax_exempt": True,
                "source_file": None,
                "source_page": None,
                "references": [],
            }
            to_import.append(row)
    for row in payload["match"]["blocked"]:
        REPORT["CUSTOMER_INVOICES_BLOCKED"] += 1
        REPORT["blocked"].append(
            {
                "ncf": row["ncf"],
                "company": row["company"],
                "reasons": row.get("match_reasons"),
            }
        )
    for row in to_import:
        try:
            import_one(env, row)
        except Exception as exc:
            env.cr.rollback()
            REPORT["CUSTOMER_INVOICES_BLOCKED"] += 1
            REPORT["errors"].append({"ncf": row.get("ncf"), "error": str(exc)})
            REPORT["blocked"].append({"ncf": row.get("ncf"), "reason": str(exc)})
    # reconcile AR
    ar = defaultdict(lambda: {"excel": Decimal("0"), "odoo": Decimal("0")})
    for row in payload["cxc"]:
        ar[row["company"]]["excel"] += _money(row["amount_residual"])
    Move = env["account.move"]
    for company_name in ar:
        company = find_company(env, company_name)
        if not company:
            continue
        moves = Move.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "=", "out_invoice"),
                ("invoice_origin", "=", payload.get("batch", BATCH)),
                ("state", "=", "posted"),
            ]
        )
        ar[company_name]["odoo"] = sum(
            (_money(m.amount_residual) for m in moves), Decimal("0")
        )
        ar[company_name]["count"] = len(moves)
    REPORT["ar"] = {
        k: {
            "EXCEL_AR_TOTAL": str(v["excel"]),
            "ODOO_AR_TOTAL": str(v["odoo"]),
            "DIFFERENCE": str(v["odoo"] - v["excel"]),
            "count": v.get("count", 0),
        }
        for k, v in ar.items()
    }
    REPORT["EXCEL_AR_TOTAL"] = str(sum((v["excel"] for v in ar.values()), Decimal("0")))
    REPORT["ODOO_AR_TOTAL"] = str(sum((v["odoo"] for v in ar.values()), Decimal("0")))
    REPORT["AR_DIFFERENCE"] = str(
        _money(REPORT["ODOO_AR_TOTAL"]) - _money(REPORT["EXCEL_AR_TOTAL"])
    )
    REPORT["EXCEL_AP_TOTAL"] = "0.00"
    REPORT["ODOO_AP_TOTAL"] = "0.00"
    REPORT["AP_DIFFERENCE"] = "NOT_APPLICABLE"
    out = Path("/tmp/opening_import_report.json")
    out.write_text(
        json.dumps(REPORT, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: REPORT[k] for k in REPORT if k not in ("products", "created_moves")},
            default=str,
            indent=2,
        )
    )
    print("WROTE", out)


run(env)
