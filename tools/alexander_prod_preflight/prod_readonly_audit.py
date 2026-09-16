# -*- coding: utf-8 -*-
"""PROD READ-ONLY audit. Never commit. Never write."""

assert env.cr.dbname == "doralex_prod"
print("DB", env.cr.dbname)
print("NO_COMMIT")


# --- versions ---
def _mod(name):
    return env["ir.module.module"].sudo().search([("name", "=", name)], limit=1)


for name in (
    "justech_alexander_base",
    "justech_alexander_ux",
    "justech_alexander_reports",
    "justech_alexander_microsoft_mail",
    "justech_approval_flow",
    "justech_l10n_do_base",
    "justech_l10n_do_ncf",
    "justech_l10n_do_payments_withholding",
    "justech_purchase_sale_margin_control",
    "justech_sale_purchase_trace",
    "multi_invoice_manual_payment_prod",
    "justech_accounting_recovery",
):
    m = _mod(name)
    print(
        "MOD",
        name,
        m.state if m else "MISSING",
        m.latest_version if m else None,
        m.installed_version if m else None,
    )

print(
    "ODOO",
    env["ir.module.module"]
    .sudo()
    .search([("name", "=", "base")], limit=1)
    .latest_version,
)

# --- companies ---
print("=== COMPANIES ===")
for c in env["res.company"].sudo().search([]):
    print(
        "CO",
        c.id,
        c.name,
        "dx=%s" % getattr(c, "dx_short_code", None),
        "vat=%s" % (c.vat or (c.partner_id.vat if c.partner_id else None)),
        "sale_appr=%s" % getattr(c, "justech_approval_sale_enabled", None),
        "po_appr=%s" % getattr(c, "justech_approval_purchase_enabled", None),
        "inv_appr=%s" % getattr(c, "justech_approval_invoice_enabled", None),
    )

# --- NCF ---
print("=== NCF RANGES ===")
Range = env["justech.do.ncf.range"].sudo()
for r in Range.search([], order="company_id, prefix, id"):
    print(
        "NCF",
        "co=%s" % r.company_id.id,
        "company=%s" % r.company_id.name,
        "tipo=%s" % r.prefix,
        "id=%s" % r.id,
        "start=%s" % r.sequence_start,
        "end=%s" % r.sequence_end,
        "next=%s" % r.next_sequence,
        "state=%s" % r.state,
        "from=%s" % r.date_from,
        "to=%s" % r.date_to,
        "auth=%s" % r.authorization_number,
        "name=%s" % r.name,
        "flow=%s" % getattr(r, "flow_kind", None),
        "journals=%s" % ",".join(r.journal_ids.mapped("code")),
    )

print("=== PURCHASE EMISSION CFG ===")
if "justech.do.purchase.emission.config" in env:
    for cfg in env["justech.do.purchase.emission.config"].sudo().search([]):
        print(
            "CFG",
            cfg.company_id.id,
            cfg.prefix,
            cfg.status,
            cfg.emission_enabled,
            "range=%s" % cfg.range_id.id,
        )

# --- DX catalog ---
print("=== DX CATALOG PROD ===")
if "justech.do.withholding.catalog" in env:
    Cat = env["justech.do.withholding.catalog"].sudo().with_context(active_test=False)
    for rec in Cat.search([("code", "like", "DX-")], order="code"):
        print(
            "DX",
            rec.code,
            rec.name,
            "rate=%s" % rec.rate,
            "base=%s" % rec.base_type,
            "active=%s" % rec.active,
            "co=%s" % rec.company_id.id,
            "tax=%s" % rec.tax_id.name if rec.tax_id else None,
        )
    print("DX_COUNT", Cat.search_count([("code", "like", "DX-")]))
    print("=== WH COMPANY CONFIG ===")
    if "justech.do.withholding.company.config" in env:
        for cfg in env["justech.do.withholding.company.config"].sudo().search([]):
            acc = cfg.account_id
            print(
                "WHCFG",
                cfg.company_id.id,
                cfg.catalog_id.code if cfg.catalog_id else None,
                "acc_id=%s" % acc.id,
                "acc_code=%s" % (acc.code if acc else None),
                "acc_name=%s" % (acc.name if acc else None),
                "acc_type=%s" % (acc.account_type if acc else None),
                "acc_cos=%s" % (acc.company_ids.ids if acc else None),
                "active=%s" % cfg.active_config,
            )
else:
    print("DX catalog model missing")

# --- expected accounts by name, resolved per company via code+type ---
NAMES = [
    ("ISR_OTHER", "Other Withholdings (N07-07)", "Other Withholdings"),
    ("ISR_RENT", "ISR withheld on rent paid to individuals", None),
    ("ISR_INT", "ISR withheld on interest paid", None),
    ("ISR_INT_EXT", "ISR Withheld on Interest Paid Abroad", None),
    ("ISR_EXT", "ISR Withheld on Remittances Abroad (L253-12)", None),
    ("ITBIS_PJ", "ITBIS Withheld from Legal Entity (N02-05)", None),
    ("ITBIS_PF", "ITBIS Withheld from Individuals (R293-11)", None),
    ("ITBIS_ESFL", "ITBIS Withheld from Non-Profit Entities (N01-11)", None),
    ("ITBIS_PROF", "ITBIS Withheld for Professional Services (N02-05)", None),
    ("ITBIS_INF", "ITBIS Withheld from Informal Goods (N08-10)", None),
]
print("=== ACCOUNTS BY COMPANY ===")
Account = env["account.account"].sudo()
ops = env["res.company"].sudo().search([("id", "!=", 1)])
for company in ops:
    print("ACC_CO", company.id, company.name)
    for key, name, alt in NAMES:
        domain = [("company_ids", "in", [company.id]), ("name", "=", name)]
        recs = Account.search(domain)
        if not recs and alt:
            recs = Account.search(
                [("company_ids", "in", [company.id]), ("name", "=", alt)]
            )
        if not recs:
            print("ACC_MISS", company.id, key, name)
            continue
        for acc in recs:
            other_cos = [i for i in acc.company_ids.ids if i != company.id]
            print(
                "ACC",
                company.id,
                key,
                "id=%s" % acc.id,
                "code=%s" % acc.code,
                "name=%s" % acc.name,
                "type=%s" % acc.account_type,
                "cos=%s" % acc.company_ids.ids,
                "shared_other=%s" % other_cos,
            )

# also dump withholding-like accounts by code prefix 21030
print("=== WH-LIKE ACCOUNTS 21030* / name ilike Withhold ===")
for acc in Account.search(
    ["|", ("code", "ilike", "21030"), ("name", "ilike", "Withhold")]
):
    print(
        "WHACC",
        "id=%s" % acc.id,
        "code=%s" % acc.code,
        "name=%s" % acc.name,
        "type=%s" % acc.account_type,
        "cos=%s" % acc.company_ids.ids,
    )

# --- legacy taxes ---
print("=== LEGACY TAXES ===")
for t in (
    env["account.tax"]
    .sudo()
    .search(
        [
            (
                "name",
                "in",
                [
                    "-10% ISR Fee",
                    "-10% ISR Rent.",
                    "-2% ISR (N07-07)",
                    "-27% ISR (L253-12)",
                ],
            )
        ]
    )
):
    print(
        "LEGACY",
        t.company_id.id,
        t.name,
        t.amount,
        t.type_tax_use,
        "active=%s" % t.active,
    )

# --- approvals ---
print("=== APPROVAL DATA ===")
if "justech.approval.request" in env:
    print("APPR_REQ", env["justech.approval.request"].sudo().search_count([]))
if "justech.approval.user.rule" in env:
    print("APPR_RULE", env["justech.approval.user.rule"].sudo().search_count([]))

# --- padron ---
print("=== PADRON ===")
cron = env.ref(
    "justech_l10n_do_base.ir_cron_justech_rnc_padron_auto_update",
    raise_if_not_found=False,
)
print("CRON", cron.id if cron else None, "active=%s" % (cron.active if cron else None))
if "justech.do.rnc.padron" in env:
    print("PADRON_ROWS", env["justech.do.rnc.padron"].sudo().search_count([]))
param = (
    env["ir.config_parameter"].sudo().get_param("justech_alexander.dgii_padron_enabled")
)
print("PADRON_PARAM", param)

# --- email (redacted) ---
print("=== MAIL SERVERS ===")
for s in env["ir.mail_server"].sudo().search([]):
    print(
        "SMTP",
        s.id,
        s.name,
        "host=%s" % s.smtp_host,
        "port=%s" % s.smtp_port,
        "user_set=%s" % bool(s.smtp_user),
        "pass_set=%s" % bool(s.smtp_pass),
        "encryption=%s" % s.smtp_encryption,
        "from_filter=%s" % getattr(s, "from_filter", None),
        "active=%s" % s.active,
        "company=%s"
        % (s.company_id.id if "company_id" in s._fields and s.company_id else None),
    )
print("=== COMPANY MAIL ===")
for c in env["res.company"].sudo().search([]):
    email = c.email or (c.partner_id.email if c.partner_id else None)
    print(
        "MAILCO",
        c.id,
        c.name,
        "email=%s" % email,
        (
            "catchall=%s" % getattr(c, "catchall_email", None)
            if hasattr(c, "catchall_email")
            else None
        ),
    )
# microsoft graph
print("=== GRAPH / MS MAIL FIELDS ===")
ms_fields = [
    f
    for f in env["res.company"]._fields
    if "microsoft" in f or "graph" in f or "azure" in f
]
print("MS_FIELDS", ms_fields)
for f in ms_fields:
    for c in env["res.company"].sudo().search([]):
        val = getattr(c, f, None)
        if val:
            shown = (
                "<SET>"
                if not isinstance(val, str)
                else (val[:4] + "…" if len(val) > 8 else "<SET>")
            )
            if f.endswith("secret") or "password" in f or "token" in f:
                shown = "SET" if val else "EMPTY"
            print("MS", c.id, f, shown)

# ir.mail_server + fetchmail
if "fetchmail.server" in env:
    for s in env["fetchmail.server"].sudo().search([]):
        print(
            "FETCH",
            s.id,
            s.name,
            s.server,
            "user_set=%s" % bool(s.user),
            "state=%s" % s.state,
        )

print("=== SYSTEM PARAMS MAIL ===")
for key in env["ir.config_parameter"].sudo().search([("key", "ilike", "mail")]):
    val = key.value or ""
    red = val
    if any(x in key.key.lower() for x in ("pass", "secret", "token", "key")):
        red = "SET" if val else "EMPTY"
    elif "@" in val:
        red = val.split("@")[-1]
    print("PARAM", key.key, red[:80])

print("READONLY_DONE")
# deliberately no env.cr.commit()
