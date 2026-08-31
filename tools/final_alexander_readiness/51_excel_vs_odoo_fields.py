# -*- coding: utf-8 -*-
"""Read-only: company native fields + all bank journals + NCF B04 + user 5."""
import json

OUT = "/tmp/excel_vs_odoo_fields.json"
rows = []
for c in env["res.company"].sudo().search([("id", "!=", 1)]):
    p = c.partner_id
    rec = {
        "id": c.id,
        "name": c.name,
        "commercial_name": getattr(c, "commercial_name", False) or "",
        "dx_trade_name": getattr(c, "dx_trade_name", False) or "",
        "dx_legal_representative": getattr(c, "dx_legal_representative", False) or "",
        "dx_legal_id_number": getattr(c, "dx_legal_id_number", False) or "",
        "account_representative_id": c.account_representative_id.name
        if getattr(c, "account_representative_id", False)
        else "",
        "l10n_do_dgii_start_date": str(getattr(c, "l10n_do_dgii_start_date", False) or ""),
        "justech_do_rnc_economic_activity": getattr(p, "justech_do_rnc_economic_activity", False)
        or "",
        "justech_do_rnc_official_name": getattr(p, "justech_do_rnc_official_name", False) or "",
        "justech_do_rnc_trade_name": getattr(p, "justech_do_rnc_trade_name", False) or "",
        "l10n_do_dgii_tax_payer_type": p.l10n_do_dgii_tax_payer_type
        if "l10n_do_dgii_tax_payer_type" in p._fields
        else "",
        "vat": p.vat or "",
        "street": p.street or "",
        "street2": p.street2 or "",
        "city": p.city or "",
        "state": p.state_id.name if p.state_id else "",
        "state_code": p.state_id.code if p.state_id else "",
        "country": p.country_id.code if p.country_id else "",
        "phone": p.phone or "",
        "email": p.email or "",
        "currency": c.currency_id.name,
    }
    rows.append(rec)

journals = []
for j in env["account.journal"].sudo().search([("type", "in", ("bank", "cash"))]):
    in_lines = []
    for line in j.inbound_payment_method_line_ids:
        in_lines.append(
            {
                "name": line.name,
                "acc": line.payment_account_id.code if line.payment_account_id else "",
                "acc_name": line.payment_account_id.name if line.payment_account_id else "",
            }
        )
    out_lines = []
    for line in j.outbound_payment_method_line_ids:
        out_lines.append(
            {
                "name": line.name,
                "acc": line.payment_account_id.code if line.payment_account_id else "",
                "acc_name": line.payment_account_id.name if line.payment_account_id else "",
            }
        )
    journals.append(
        {
            "company": j.company_id.name,
            "cid": j.company_id.id,
            "id": j.id,
            "name": j.name,
            "code": j.code,
            "type": j.type,
            "bank_acc": j.bank_account_id.acc_number if j.bank_account_id else "",
            "gl": j.default_account_id.code if j.default_account_id else "",
            "gl_name": j.default_account_id.name if j.default_account_id else "",
            "inbound": in_lines,
            "outbound": out_lines,
        }
    )

ncf = []
if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].sudo().search([], order="company_id, prefix"):
        ncf.append(
            {
                "company": r.company_id.name,
                "cid": r.company_id.id,
                "prefix": r.prefix,
                "start": r.sequence_start if "sequence_start" in r._fields else "",
                "end": r.sequence_end if "sequence_end" in r._fields else "",
                "next": r.next_sequence if "next_sequence" in r._fields else "",
                "left": r.remaining_count if "remaining_count" in r._fields else "",
                "exp": str(getattr(r, "expiration_date", False) or ""),
                "state": r.state if "state" in r._fields else "",
                "create_uid": r.create_uid.login if r.create_uid else "",
                "create_date": str(r.create_date or ""),
            }
        )

u = env["res.users"].sudo().browse(5)
user5 = {
    "id": u.id,
    "login": u.login,
    "name": u.name,
    "email": u.email,
    "phone": u.phone if "phone" in u._fields else "",
    "default_company": (u.company_id.id, u.company_id.name),
    "allowed": [(c.id, c.name) for c in u.company_ids],
    "active": u.active,
}

# outstanding accounts existence (not invent)
out_accs = env["account.account"].sudo().search(
    [("name", "ilike", "Outstanding")]
)
out_list = [
    (
        a.company_ids.ids if "company_ids" in a._fields else [],
        a.code,
        a.name,
    )
    for a in out_accs
]

# real vs qa partners sample
real_c = env["res.partner"].sudo().search(
    [
        ("customer_rank", ">", 0),
        ("name", "not ilike", "DXQA"),
        ("parent_id", "=", False),
    ],
    limit=20,
)
real_v = env["res.partner"].sudo().search(
    [
        ("supplier_rank", ">", 0),
        ("name", "not ilike", "DXQA"),
        ("parent_id", "=", False),
    ],
    limit=20,
)

data = {
    "companies": rows,
    "journals": journals,
    "ncf": ncf,
    "user5": user5,
    "outstanding_accounts": out_list,
    "real_customers": [(p.id, p.name, p.company_id.name, p.email) for p in real_c],
    "real_vendors": [(p.id, p.name, p.company_id.name, p.email) for p in real_v],
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
print("WROTE", OUT)
print("USER5", user5)
print("NCF_TYPES", sorted({n["prefix"] for n in ncf}))
print("JOURNALS", [(j["cid"], j["name"], j["bank_acc"], j["gl"], j["inbound"], j["outbound"]) for j in journals])
print("OUT_ACCS", len(out_list))
print("REAL_C", data["real_customers"])
print("REAL_V", data["real_vendors"])
