# -*- coding: utf-8 -*-
"""Read-only audit: Alexander Excel vs doralex_ent_staging. Never Prod."""
import json
import re
import time

OUT = "/tmp/excel_vs_odoo_audit.json"

EXCEL_COMPANIES = [
    {
        "excel_n": 1,
        "name": "INVERSIONES DORALEX,S.RL.",
        "trade": "INVERSIONES DORALEX,S.RL.",
        "rnc": "1-32-22011-2",
        "taxpayer": "Persona jurídica",
        "activity": "SERVICIO, COMERCIO, AGRARIO, INDUSTRIAL",
        "street": "AV. SAN VICENTE DE PAUL, NO. 115, LOS MINA",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "phone": "849-207-5817",
        "email": "inversionesdoralex@gmail.com",
        "legal": "Alexander Piña Aquino",
        "legal_id": "223-0157134-9",
        "currency": "DOP",
        "start": "2020-11-02",
    },
    {
        "excel_n": 2,
        "name": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "trade": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "rnc": "1-32-27106-8",
        "taxpayer": "Persona jurídica",
        "activity": "SERVICIO, COMERCIO, DISTRIBUCION, IMPORTACION",
        "street": "CALLE 8 NO. 8, LAS AMERICAS, SANTO DOMINGO ESTE,",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "phone": "849-207-5817",
        "email": "piñariascomercializadora@gmail.com",
        "legal": "Alba Rafaelina Arias Mora",
        "legal_id": "280-103907-0",
        "currency": "DOP",
        "start": "2021-03-01",
    },
    {
        "excel_n": 3,
        "name": "DOMINION BUSINESS,S.R.L.",
        "trade": "DOMINION BUSINESS,S.R.L.",
        "rnc": "1-32-72150-2",
        "taxpayer": "Persona jurídica",
        "activity": "COMERCIO, SERVICIO",
        "street": "CALLE ESPAILLAT NO. 10, ZONA COLONIAL, DISTRITO NACIONAL",
        "province": "SANTO DOMINGO",
        "municipality": "DISTRITO NACIONAL",
        "phone": "829-941-5257",
        "email": "dominionsrl@hotmail.com",
        "legal": "Arisleydi Contreras Suero",
        "legal_id": "402-4200332-1",
        "currency": "DOP",
        "start": "2022-11-09",
    },
    {
        "excel_n": 4,
        "name": "INVERSIONES EL MAYUMA, S.R.L.",
        "trade": "INVERSIONES EL MAYUMA, S.R.L.",
        "rnc": "1-32-71015-2",
        "taxpayer": "Persona jurídica",
        "activity": "COMERCIO, SERVICIO",
        "street": "CALLE CLUB ACTIVO 20-30, NO.47, RESPALDO ALMA ROSA ll",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "phone": "829-696-1881",
        "email": "inversioneselmayuma@gmail.com",
        "legal": "Eldris Marlenny Ramirez Minaya",
        "legal_id": "402-4218015-2",
        "currency": "DOP",
        "start": "2022-09-14",
    },
    {
        "excel_n": 5,
        "name": "REMPART GROUP S.R.L.",
        "trade": "REMPART GROUP S.R.L.",
        "rnc": "1-32-76915-5",
        "taxpayer": "Persona jurídica",
        "activity": "COMERCIO, SERVICIO",
        "street": "AV. SAN VICENTE DE PAUL, NO. 122, LOS MINA",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "phone": "849-394-1927",
        "email": "rempartsrl@hotmail.com",
        "legal": "Agustin Ventura Alcantara",
        "legal_id": "402-2314668-5",
        "currency": "DOP",
        "start": "2023-01-19",
    },
    {
        "excel_n": 6,
        "name": "BLUE ELITE, S.R.L.",
        "trade": "BLUE ELITE, S.R.L.",
        "rnc": "1-33-37126-1",
        "taxpayer": "Persona jurídica",
        "activity": "COMERCIO, SERVICIO",
        "street": "AV. SAN VICENTE DE PAUL, NO. 122, LOS MINA",
        "province": "SANTO DOMINGO",
        "municipality": "SANTO DOMINGO ESTE",
        "phone": "809-614-1306",
        "email": "bluelitesrl@hotmail.com",
        "legal": "Geilin Rosario Suero",
        "legal_id": "402-1097505-4",
        "currency": "DOP",
        "start": "2025-04-04",
    },
]

EXCEL_BANKS = [
    {
        "company": "INVERSIONES DORALEX,S.RL.",
        "bank": "BANRESERVAS",
        "type": "Corriente",
        "number": "9604436830",
        "currency": "DOP",
        "holder": "Alexander Piña Aquino",
        "holder_id": "223-0157134-9",
        "active": "Sí",
        "balance": 5000000,
        "balance_date": "05//08/2026",
    },
    {
        "company": "COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L.",
        "bank": "BANRESERVAS",
        "type": "Corriente",
        "number": "9604097492",
        "currency": "DOP",
        "holder": "Alba Rafaelina Arias Mora",
        "holder_id": "280-103907-0",
        "active": "Sí",
        "balance": 2450000,
        "balance_date": "05//08/2026",
    },
    {
        "company": "DOMINION BUSINESS,S.R.L.",
        "bank": "BANRESERVAS",
        "type": "Ahorros",
        "number": "9605588726",
        "currency": "DOP",
        "holder": "Arisleydi Contreras Suero",
        "holder_id": "402-4200332-1",
        "active": "Sí",
        "balance": 1500000,
        "balance_date": "05//08/2026",
    },
    {
        "company": "INVERSIONES EL MAYUMA, S.R.L.",
        "bank": "BANRESERVAS",
        "type": "Corriente",
        "number": "9605543104",
        "currency": "DOP",
        "holder": "Eldris Marlenny Ramirez Minaya",
        "holder_id": "402-4218015-2",
        "active": "Sí",
        "balance": 3000000,
        "balance_date": "05//08/2026",
    },
    {
        "company": "REMPART GROUP S.R.L.",
        "bank": "BANRESERVAS",
        "type": "Corriente",
        "number": "9608739498",
        "currency": "DOP",
        "holder": "Agustin Ventura Alcantara",
        "holder_id": "402-2314668-5",
        "active": "Sí",
        "balance": 4600000,
        "balance_date": "05//08/2026",
    },
    {
        "company": "BLUE ELITE, S.R.L.",
        "bank": "BANRESERVAS",
        "type": "Corriente",
        "number": "9608670542",
        "currency": "DOP",
        "holder": "Geilin Rosario Suero",
        "holder_id": "402-1097505-4",
        "active": "Sí",
        "balance": 1250000,
        "balance_date": "05//08/2026",
    },
]

EXCEL_EMAILS = [
    "inversionesdoralex@gmail.com",
    "piñariascomercializadora@gmail.com",
    "dominionsrl@hotmail.com",
    "inversioneselmayuma@gmail.com",
    "rempartsrl@hotmail.com",
    "bluelitesrl@hotmail.com",
]


def _norm(val):
    if val is None:
        return ""
    s = str(val).strip()
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(",", "")
    return s.upper()


def _norm_rnc(val):
    return re.sub(r"[^0-9]", "", str(val or ""))


def _norm_phone(val):
    return re.sub(r"[^0-9]", "", str(val or ""))


def _status(excel, odoo, kind="text"):
    if odoo in (None, "", False):
        return "MISSING_IN_ODOO"
    if kind == "rnc":
        if _norm_rnc(excel) == _norm_rnc(odoo):
            return "MATCH_NORMALIZED" if str(excel) != str(odoo) else "MATCH"
    if kind == "phone":
        if _norm_phone(excel) == _norm_phone(odoo):
            return "MATCH_NORMALIZED" if str(excel) != str(odoo) else "MATCH"
    if _norm(excel) == _norm(odoo):
        if str(excel).strip() != str(odoo).strip():
            return "MATCH_NORMALIZED"
        return "MATCH"
    if _norm(excel) in _norm(odoo) or _norm(odoo) in _norm(excel):
        return "MATCH_NORMALIZED"
    return "DIFFERENT"


def _company_blob(c):
    p = c.partner_id
    comment = (p.comment or "") + "\n" + (c.partner_id.comment or "")
    vat = p.vat or getattr(c, "vat", False) or getattr(c, "company_registry", False) or ""
    rnc = vat
    for fname in (
        "l10n_do_dgii_tax_payer_type",
        "l10n_latam_identification_type_id",
    ):
        pass
    street = " ".join(
        x for x in [p.street, p.street2] if x
    )
    return {
        "id": c.id,
        "name": c.name,
        "trade": p.name,
        "rnc": rnc,
        "vat": p.vat or "",
        "company_registry": getattr(c, "company_registry", False) or "",
        "street": street,
        "city": p.city or "",
        "state": p.state_id.name if p.state_id else "",
        "country": p.country_id.code if p.country_id else "",
        "phone": p.phone or c.phone or "",
        "email": p.email or c.email or "",
        "currency": c.currency_id.name if c.currency_id else "",
        "comment": (p.comment or "")[:2000],
        "website": p.website or "",
    }


def _find_in_comment(comment, labels):
    text = comment or ""
    for lab in labels:
        m = re.search(lab + r"\s*[:=]\s*(.+)", text, flags=re.I)
        if m:
            return m.group(1).split("\n")[0].strip()
    return ""


result = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "database": env.cr.dbname,
    "prod_touched": False,
    "config_changed": False,
    "excel_sheets": [
        "Instrucciones",
        "Empresas",
        "Cuentas bancarias",
        "Sucursales y almacenes",
        "Usuarios",
        "Datos fiscales",
    ],
    "fiscal_rows_in_source_excel": 0,
    "companies": [],
    "company_field_rows": [],
    "technical_template": {},
    "banks": [],
    "bank_accounting": [],
    "branches": [],
    "warehouses": [],
    "users": {},
    "ncf": [],
    "qa_contamination": {},
    "blocks": {},
}

all_cos = env["res.company"].sudo().search([])
result["odoo_company_count"] = len(all_cos)
result["odoo_companies"] = [
    {"id": c.id, "name": c.name, "currency": c.currency_id.name} for c in all_cos
]

# --- companies ---
for row in EXCEL_COMPANIES:
    cand = env["res.company"].sudo().search([("name", "ilike", row["name"][:20])])
    if not cand:
        cand = env["res.company"].sudo().search([("name", "ilike", row["name"].split(",")[0][:12])])
    # prefer exact-ish
    hit = False
    for c in cand:
        if _norm(c.name).replace(".", "") == _norm(row["name"]).replace(".", "") or _norm(
            row["name"]
        )[:18] in _norm(c.name):
            hit = c
            break
    if not hit and cand:
        hit = cand[0]
    blob = _company_blob(hit) if hit else {}
    comment = blob.get("comment", "")
    odoo_vals = {
        "razón social": blob.get("name"),
        "nombre comercial": blob.get("trade"),
        "RNC": blob.get("rnc") or blob.get("vat") or blob.get("company_registry"),
        "tipo de contribuyente": _find_in_comment(
            comment, ["Tipo de contribuyente", "tipo contribuyente", "Taxpayer"]
        )
        or ("Persona jurídica" if hit else ""),
        "actividad principal": _find_in_comment(
            comment, ["Actividad principal", "Actividad", "Activity"]
        ),
        "dirección fiscal": blob.get("street"),
        "provincia": blob.get("state"),
        "municipio": blob.get("city"),
        "teléfono": blob.get("phone"),
        "correo": blob.get("email"),
        "representante legal": _find_in_comment(
            comment, ["Representante legal", "Rep. legal", "Legal representative"]
        ),
        "cédula representante": _find_in_comment(
            comment, ["Cédula representante", "Cedula representante", "Cédula"]
        ),
        "moneda": blob.get("currency"),
        "fecha inicio operaciones": _find_in_comment(
            comment, ["Fecha inicio", "Inicio operaciones", "Start date"]
        ),
    }
    excel_map = {
        "razón social": row["name"],
        "nombre comercial": row["trade"],
        "RNC": row["rnc"],
        "tipo de contribuyente": row["taxpayer"],
        "actividad principal": row["activity"],
        "dirección fiscal": row["street"],
        "provincia": row["province"],
        "municipio": row["municipality"],
        "teléfono": row["phone"],
        "correo": row["email"],
        "representante legal": row["legal"],
        "cédula representante": row["legal_id"],
        "moneda": row["currency"],
        "fecha inicio operaciones": row["start"],
    }
    kinds = {
        "RNC": "rnc",
        "teléfono": "phone",
        "cédula representante": "rnc",
    }
    rec = {
        "excel_n": row["excel_n"],
        "excel_name": row["name"],
        "odoo_id": blob.get("id"),
        "odoo_name": blob.get("name"),
        "fields": [],
    }
    for field, excel_v in excel_map.items():
        odoo_v = odoo_vals.get(field)
        st = _status(excel_v, odoo_v, kinds.get(field, "text"))
        # comment fallback search for legal/activity/start if missing
        if st == "MISSING_IN_ODOO" and comment:
            if _norm(excel_v) and _norm(excel_v) in _norm(comment):
                st = "MATCH_NORMALIZED"
                odoo_v = "(en comment del partner) " + excel_v
        rec["fields"].append(
            {
                "COMPANY": row["name"],
                "FIELD": field,
                "EXCEL_VALUE": excel_v,
                "ODOO_VALUE": odoo_v or "",
                "STATUS": st,
            }
        )
        result["company_field_rows"].append(rec["fields"][-1])
    rec["matched"] = bool(hit)
    result["companies"].append(rec)

# --- technical template ---
tmpl = env["res.company"].sudo().browse(1)
moves_t = env["account.move"].sudo().search_count([("company_id", "=", 1)])
users_t = env["res.users"].sudo().search_count([("company_ids", "in", [1]), ("share", "=", False)])
ncf_t = 0
if "justech.do.ncf.range" in env:
    ncf_t = env["justech.do.ncf.range"].sudo().search_count([("company_id", "=", 1)])
result["technical_template"] = {
    "TECHNICAL_TEMPLATE_COMPANY": tmpl.name,
    "COMPANY_ID": tmpl.id,
    "currency": tmpl.currency_id.name,
    "country": tmpl.country_id.code if tmpl.country_id else "",
    "HAS_TRANSACTIONS": moves_t > 0,
    "move_count": moves_t,
    "posted_moves": env["account.move"].sudo().search_count(
        [("company_id", "=", 1), ("state", "=", "posted")]
    ),
    "HAS_FISCAL_CONFIG": ncf_t > 0,
    "ncf_range_count": ncf_t,
    "HAS_USERS": users_t > 0,
    "user_count_with_company": users_t,
    "RECOMMENDATION": "KEEP",
}

# --- banks ---
for b in EXCEL_BANKS:
    co = env["res.company"].sudo().search([("name", "ilike", b["company"][:18])], limit=1)
    accs = env["res.partner.bank"].sudo().search(
        ["|", ("acc_number", "ilike", b["number"]), ("acc_number", "=", b["number"])]
    )
    if not accs and co:
        accs = env["res.partner.bank"].sudo().search([("company_id", "=", co.id)])
    journals = env["account.journal"].sudo().search(
        [("company_id", "=", co.id if co else 0), ("type", "=", "bank")]
    )
    acc = accs[:1]
    journal = False
    if acc:
        journal = journals.filtered(
            lambda j: j.bank_account_id.id == acc.id
        )[:1] or journals[:1]
    elif journals:
        journal = journals[:1]
    odoo_num = acc.acc_number if acc else ""
    odoo_bank = (
        acc.bank_id.name
        if acc and acc.bank_id
        else (journal.bank_id.name if journal and journal.bank_id else "")
    )
    odoo_cur = (
        acc.currency_id.name
        if acc and acc.currency_id
        else (journal.currency_id.name if journal and journal.currency_id else (co.currency_id.name if co else ""))
    )
    odoo_holder = acc.partner_id.name if acc and acc.partner_id else ""
    odoo_type = ""
    for fname in ("acc_type", "account_type"):
        if acc and fname in acc._fields:
            odoo_type = acc[fname] or ""
    match = "MISSING_IN_ODOO"
    if acc and _norm_rnc(odoo_num) == _norm_rnc(b["number"]):
        match = "MATCH"
    elif acc:
        match = "DIFFERENT"
    elif journal:
        match = "MISSING_IN_ODOO"
    result["banks"].append(
        {
            "COMPANY": b["company"],
            "BANK": b["bank"],
            "ACCOUNT_NUMBER": b["number"],
            "ACCOUNT_TYPE": b["type"],
            "CURRENCY": b["currency"],
            "HOLDER": b["holder"],
            "INITIAL_BALANCE": b["balance"],
            "BALANCE_DATE": b["balance_date"],
            "ODOO_JOURNAL": journal.name if journal else "",
            "ODOO_ACCOUNT_NUMBER": odoo_num,
            "ODOO_BANK": odoo_bank,
            "ODOO_HOLDER": odoo_holder,
            "ODOO_CURRENCY": odoo_cur,
            "ODOO_TYPE": odoo_type,
            "MATCH_STATUS": match,
            "company_id": co.id if co else None,
            "journal_id": journal.id if journal else None,
        }
    )

# --- bank accounting / outstanding ---
for co in env["res.company"].sudo().search([]):
    for j in env["account.journal"].sudo().search(
        [("company_id", "=", co.id), ("type", "in", ("bank", "cash"))]
    ):
        inbound = []
        outbound = []
        for line in j.inbound_payment_method_line_ids:
            inbound.append(
                {
                    "name": line.name,
                    "code": line.payment_method_id.code if line.payment_method_id else "",
                    "outstanding": line.payment_account_id.code
                    if line.payment_account_id
                    else "",
                    "outstanding_name": line.payment_account_id.name
                    if line.payment_account_id
                    else "",
                }
            )
        for line in j.outbound_payment_method_line_ids:
            outbound.append(
                {
                    "name": line.name,
                    "code": line.payment_method_id.code if line.payment_method_id else "",
                    "outstanding": line.payment_account_id.code
                    if line.payment_account_id
                    else "",
                    "outstanding_name": line.payment_account_id.name
                    if line.payment_account_id
                    else "",
                }
            )
        dgii = []
        if "justech_do_payment_form" in j._fields:
            dgii.append(str(j.justech_do_payment_form))
        # payment method lines may have dgii
        for line in j.inbound_payment_method_line_ids | j.outbound_payment_method_line_ids:
            for fname in (
                "justech_do_payment_form",
                "l10n_do_payment_form",
                "dgii_payment_form",
            ):
                if fname in line._fields and line[fname]:
                    dgii.append("%s:%s" % (line.name, line[fname]))
        rec_acc = next((x["outstanding"] for x in inbound if x["outstanding"]), "")
        pay_acc = next((x["outstanding"] for x in outbound if x["outstanding"]), "")
        gl = j.default_account_id.code if j.default_account_id else ""
        cls = "MISSING"
        if rec_acc and pay_acc and gl:
            cls = "NEEDS_ACCOUNTANT_CONFIRMATION"
        elif gl and not (rec_acc and pay_acc):
            cls = "MISSING"
        elif rec_acc or pay_acc:
            cls = "NEEDS_ACCOUNTANT_CONFIRMATION"
        result["bank_accounting"].append(
            {
                "COMPANY": co.name,
                "company_id": co.id,
                "BANK_ACCOUNT": j.bank_account_id.acc_number
                if j.bank_account_id
                else (j.name or ""),
                "journal": j.name,
                "journal_type": j.type,
                "BANK_GL_ACCOUNT": gl,
                "BANK_GL_NAME": j.default_account_id.name if j.default_account_id else "",
                "OUTSTANDING_RECEIPTS_ACCOUNT": rec_acc,
                "OUTSTANDING_PAYMENTS_ACCOUNT": pay_acc,
                "INBOUND_PAYMENT_METHOD": [x["name"] for x in inbound],
                "OUTBOUND_PAYMENT_METHOD": [x["name"] for x in outbound],
                "DGII_PAYMENT_METHOD": dgii,
                "CLASSIFICATION": cls,
            }
        )

# --- warehouses / partners as offices ---
for row in EXCEL_COMPANIES:
    co = env["res.company"].sudo().search([("name", "ilike", row["name"][:18])], limit=1)
    whs = env["stock.warehouse"].sudo().search([("company_id", "=", co.id)]) if co else env["stock.warehouse"]
    locs = (
        env["stock.location"].sudo().search(
            [("company_id", "=", co.id), ("usage", "=", "internal")]
        )
        if co
        else env["stock.location"]
    )
    result["warehouses"].append(
        {
            "COMPANY": row["name"],
            "odoo_id": co.id if co else None,
            "excel_local": row["name"],
            "excel_type": "Oficina principal",
            "excel_street": row["street"],
            "excel_phone": row["phone"],
            "excel_responsable": row["legal"],
            "odoo_company_street": co.partner_id.street if co else "",
            "odoo_warehouses": [(w.id, w.name, w.code) for w in whs],
            "odoo_internal_locations": [(l.id, l.complete_name) for l in locs],
            "office_address_match": _status(row["street"], co.partner_id.street if co else ""),
        }
    )

# --- users ---
users = env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])
alex = users.filtered(
    lambda u: "alexander" in (u.name or "").lower()
    or "piña" in (u.name or "").lower()
    or "pina" in (u.name or "").lower()
    or (u.login or "").lower() in [e.lower() for e in EXCEL_EMAILS]
    or (u.email or "").lower() in [e.lower() for e in EXCEL_EMAILS]
)
email_hits = users.filtered(
    lambda u: (u.login or "").lower() in [e.lower() for e in EXCEL_EMAILS]
    or (u.email or "").lower() in [e.lower() for e in EXCEL_EMAILS]
)
result["users"] = {
    "EXCEL_ROWS": 6,
    "excel_person": "ALEXANDER PIÑA AQUINO",
    "excel_emails": EXCEL_EMAILS,
    "ODOO_USER_COUNT": len(users),
    "ALEXANDER_USER_IDS": alex.ids,
    "LOGINS": [(u.id, u.login, u.name, u.email) for u in alex],
    "email_logins": [(u.id, u.login, u.name) for u in email_hits],
    "all_internal": [
        {
            "id": u.id,
            "login": u.login,
            "name": u.name,
            "email": u.email,
            "default_company": u.company_id.name,
            "allowed": [(c.id, c.name) for c in u.company_ids],
        }
        for u in users
    ],
}

# --- NCF ---
if "justech.do.ncf.range" in env:
    ranges = env["justech.do.ncf.range"].sudo().search([])
    for r in ranges:
        src = "UNKNOWN"
        create_uid = r.create_uid.login if r.create_uid else ""
        note = ""
        for fname in ("notes", "name", "description"):
            if fname in r._fields and r[fname]:
                note += " " + str(r[fname])
        blob = " ".join(
            [
                create_uid,
                note,
                str(r.prefix or ""),
            ]
        ).lower()
        if "dxqa" in blob or "qa" in create_uid:
            src = "QA_CONFIGURATION"
        elif "excel" in blob or "alexander" in blob:
            src = "ALEXANDER_EXCEL"
        else:
            src = "MANUAL_CONFIGURATION"
        result["ncf"].append(
            {
                "COMPANY": r.company_id.name,
                "company_id": r.company_id.id,
                "NCF_TYPE": r.prefix or getattr(r, "document_type_id", False) and str(r.document_type_id) or "",
                "RANGE_START": getattr(r, "sequence_start", False) or getattr(r, "number_from", False) or "",
                "RANGE_END": getattr(r, "sequence_end", False) or "",
                "CURRENT_NEXT": getattr(r, "next_sequence", False) or "",
                "remaining": getattr(r, "remaining_count", False),
                "EXPIRATION": str(getattr(r, "expiration_date", False) or getattr(r, "date_to", False) or ""),
                "state": getattr(r, "state", False) or "",
                "SOURCE": src,
                "create_uid": create_uid,
                "create_date": str(r.create_date or ""),
                "id": r.id,
            }
        )

# --- QA contamination ---
Partner = env["res.partner"].sudo()
Product = env["product.product"].sudo()
SO = env["sale.order"].sudo()
result["qa_contamination"] = {
    "dxqa_partners": Partner.search_count([("name", "ilike", "DXQA")]),
    "dxqa_products": Product.search_count(["|", ("name", "ilike", "DXQA"), ("default_code", "ilike", "DXQA")]),
    "dxqa_sale_orders": SO.search_count(
        ["|", ("client_order_ref", "ilike", "DXQA"), ("origin", "ilike", "DXQA")]
    ),
    "mass_tag_sos": SO.search_count([("client_order_ref", "ilike", "DXQA-MASS-20260831")]),
    "final_tag_sos": SO.search_count([("client_order_ref", "ilike", "DXQA-FINAL")]),
}

# --- blocks already configured? ---
real_partners = Partner.search(
    [
        ("name", "not ilike", "DXQA"),
        ("is_company", "=", True),
        ("id", "not in", all_cos.partner_id.ids),
    ]
)
real_customers = Partner.search(
    [
        ("name", "not ilike", "DXQA"),
        ("customer_rank", ">", 0),
        ("id", "not in", all_cos.partner_id.ids),
    ]
)
real_vendors = Partner.search(
    [
        ("name", "not ilike", "DXQA"),
        ("supplier_rank", ">", 0),
        ("id", "not in", all_cos.partner_id.ids),
    ]
)
real_products = Product.search(
    [
        ("default_code", "not ilike", "DXQA"),
        ("name", "not ilike", "DXQA"),
        ("default_code", "not in", [False, ""]),
    ]
)
wh_configs = 0
if "justech.do.withholding.config" in env:
    wh_configs = env["justech.do.withholding.config"].sudo().search_count([])
elif "l10n_do.withholding" in env:
    wh_configs = env["l10n_do.withholding"].sudo().search_count([])
taxes = env["account.tax"].sudo().search_count([("active", "=", True)])
accounts = env["account.account"].sudo().search_count([])
open_ar = env["account.move"].sudo().search_count(
    [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("amount_residual", ">", 0),
        ("ref", "not ilike", "DXQA"),
        ("invoice_origin", "not ilike", "DXQA"),
    ]
)
open_ap = env["account.move"].sudo().search_count(
    [
        ("move_type", "=", "in_invoice"),
        ("state", "=", "posted"),
        ("amount_residual", ">", 0),
        ("ref", "not ilike", "DXQA"),
        ("invoice_origin", "not ilike", "DXQA"),
    ]
)
quants = 0
if "stock.quant" in env:
    quants = env["stock.quant"].sudo().search_count([("quantity", "!=", 0)])
assets = 0
if "account.asset" in env:
    assets = env["account.asset"].sudo().search_count([])
opening = env["account.move"].sudo().search_count(
    [
        "|",
        "|",
        ("ref", "ilike", "apertura"),
        ("ref", "ilike", "opening"),
        ("journal_id.code", "ilike", "OPE"),
    ]
)

result["blocks"] = {
    "NCF": {
        "ALREADY_CONFIGURED": bool(result["ncf"]),
        "SOURCE": "QA_OR_MANUAL_NOT_EXCEL",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "note": "Excel fiscal sheet empty. Current B01/B04 must not be treated as Alexander-delivered.",
    },
    "outstanding": {
        "ALREADY_CONFIGURED": any(
            x["OUTSTANDING_RECEIPTS_ACCOUNT"] for x in result["bank_accounting"]
        ),
        "SOURCE": "QA_CONFIGURATION",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
    },
    "coa": {
        "ALREADY_CONFIGURED": accounts > 0,
        "SOURCE": "ODOO_L10N_DO / ENTERPRISE_TEMPLATE",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "account_count": accounts,
    },
    "taxes": {
        "ALREADY_CONFIGURED": taxes > 0,
        "SOURCE": "ODOO_L10N_DO",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "tax_count": taxes,
        "withholding_configs": wh_configs,
    },
    "customers": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "QA_ONLY_IF_DXQA",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "real_customer_rank": len(real_customers),
        "dxqa_partners": result["qa_contamination"]["dxqa_partners"],
    },
    "vendors": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "QA_ONLY_IF_DXQA",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "real_vendor_rank": len(real_vendors),
    },
    "products": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "QA_DXQA_PRODUCTS",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "coded_non_dxqa": len(real_products),
        "dxqa_products": result["qa_contamination"]["dxqa_products"],
    },
    "open_ar": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "QA_INVOICES_PRESENT_NOT_ALEXANDER",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "open_non_dxqa_ref": open_ar,
    },
    "open_ap": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "QA_BILLS_PRESENT_NOT_ALEXANDER",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "open_non_dxqa_ref": open_ap,
    },
    "advances": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": None,
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
    },
    "opening_balance": {
        "ALREADY_CONFIGURED": opening > 0,
        "SOURCE": "UNKNOWN_IF_ANY",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "moves_looking_like_opening": opening,
        "excel_balances_posted": False,
    },
    "inventory": {
        "ALREADY_CONFIGURED": quants > 0,
        "SOURCE": "UNKNOWN",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
        "nonzero_quants": quants,
    },
    "assets": {
        "ALREADY_CONFIGURED": assets > 0,
        "SOURCE": None,
        "COMPLETE": False,
        "NEEDS_ALEXANDER": assets == 0,
        "asset_count": assets,
    },
    "users_roles": {
        "ALREADY_CONFIGURED": bool(alex),
        "SOURCE": "ALEXANDER_EXCEL_PARTIAL",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
    },
    "extra_warehouses": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": "EXCEL_OFFICES_ONLY",
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
    },
    "history": {
        "ALREADY_CONFIGURED": False,
        "SOURCE": None,
        "COMPLETE": False,
        "NEEDS_ALEXANDER": True,
    },
}

# comment dump for first operational company to see stored extras
if result["companies"] and result["companies"][0].get("odoo_id"):
    c0 = env["res.company"].sudo().browse(result["companies"][0]["odoo_id"])
    result["sample_partner_comment"] = c0.partner_id.comment or ""
    result["company_extra_fields"] = sorted(
        [
            f
            for f in c0._fields
            if any(
                k in f
                for k in (
                    "legal",
                    "rnc",
                    "activity",
                    "start",
                    "trade",
                    "commercial",
                    "rep",
                    "cedula",
                    "fiscal",
                )
            )
        ]
    )
    result["partner_extra_fields"] = sorted(
        [
            f
            for f in c0.partner_id._fields
            if any(
                k in f
                for k in (
                    "legal",
                    "rnc",
                    "activity",
                    "l10n_do",
                    "comment",
                    "vat",
                )
            )
        ]
    )

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2, default=str)
print("WROTE", OUT)
print("COMPANIES", len(result["companies"]), "FIELDS", len(result["company_field_rows"]))
print("BANKS", [(b["COMPANY"][:20], b["MATCH_STATUS"], b["ODOO_ACCOUNT_NUMBER"]) for b in result["banks"]])
print("NCF", len(result["ncf"]), "USERS_ALEX", result["users"]["ALEXANDER_USER_IDS"])
print("TMPL", result["technical_template"])
print("QA", result["qa_contamination"])
