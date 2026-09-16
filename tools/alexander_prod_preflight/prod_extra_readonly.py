# -*- coding: utf-8 -*-
"""PROD extra READ-ONLY. Never commit."""

assert env.cr.dbname == "doralex_prod"
print("EXTRA_DB", env.cr.dbname)

# approval / padron params
Icp = env["ir.config_parameter"].sudo()
for k in (
    "justech_alexander.approval_flow_enabled",
    "justech_alexander.dgii_padron_enabled",
    "justech_alexander.ecf_operational_enabled",
    "justech.approval.public.base.url",
    "web.base.url",
):
    print("PARAM", k, repr(Icp.get_param(k)))

# padron partner/invoice block signals
Partner = env["res.partner"].sudo()
fields_p = [
    f for f in Partner._fields if "padron" in f or "fiscal_config" in f or "rnc" in f
]
print("PARTNER_FISCAL_FIELDS", fields_p)
if "justech_do_fiscal_config_state" in Partner._fields:
    print(
        "PARTNER_STATE_COUNTS",
        Partner.read_group(
            [], ["justech_do_fiscal_config_state"], ["justech_do_fiscal_config_state"]
        ),
    )

# rnc padron config model
if "justech.do.rnc.padron.config" in env:
    for rec in env["justech.do.rnc.padron.config"].sudo().search([]):
        print(
            "PADRON_CFG",
            rec.id,
            {
                f: getattr(rec, f)
                for f in rec._fields
                if any(
                    x in f
                    for x in ("active", "enable", "block", "auto", "cron", "company")
                )
            },
        )

# ITBIS taxes
print("=== ITBIS TAXES ===")
for t in (
    env["account.tax"]
    .sudo()
    .search([("name", "ilike", "ITBIS")], order="company_id, amount")
):
    if t.company_id.id == 1:
        continue
    if (
        abs(t.amount) in (16.0, 18.0)
        or "16" in (t.name or "")
        or "18" in (t.name or "")
    ):
        print(
            "TAX",
            t.company_id.id,
            t.name,
            t.amount,
            t.type_tax_use,
            "active=%s" % t.active,
            "price_include=%s" % t.price_include,
        )

# account extra identifiers
print("=== ACCOUNT IDENTIFIERS SAMPLE ===")
acc = env["account.account"].sudo().browse(1897)
print(
    "ACC_FIELDS",
    [f for f in acc._fields if "code" in f or "xml" in f or "group" in f][:40],
)
print(
    "ACC1897",
    "code=%r" % acc.code,
    "name=%s" % acc.name,
    "type=%s" % acc.account_type,
    "cos=%s" % acc.company_ids.ids,
)
for f in ("code_store", "code_mapping", "group_id"):
    if f in acc._fields:
        print("ACC1897", f, getattr(acc, f))
xmlids = acc.get_external_id()
print("ACC1897_XMLID", xmlids)

# mail extra
print("=== MAIL EXTRA ===")
print("SMTP_COUNT", env["ir.mail_server"].sudo().search_count([]))
for s in env["ir.mail_server"].sudo().search([]):
    print(
        "SMTP",
        s.id,
        s.name,
        "host=%s" % s.smtp_host,
        "port=%s" % s.smtp_port,
        "user_set=%s" % bool(s.smtp_user),
        "enc=%s" % s.smtp_encryption,
        "active=%s" % s.active,
        "from=%s" % getattr(s, "from_filter", None),
    )
if "fetchmail.server" in env:
    print("FETCH_COUNT", env["fetchmail.server"].sudo().search_count([]))
    for s in env["fetchmail.server"].sudo().search([]):
        print(
            "FETCH",
            s.id,
            s.name,
            "state=%s" % s.state,
            "server=%s" % s.server,
            "user_set=%s" % bool(s.user),
        )
if "mail.alias.domain" in env:
    for d in env["mail.alias.domain"].sudo().search([]):
        print(
            "ALIASDOM",
            d.name,
            "default=%s" % getattr(d, "sequence", None),
            "company=%s"
            % (d.company_id.id if "company_id" in d._fields and d.company_id else None),
        )
for model in sorted(env):
    if any(x in model for x in ("microsoft", "graph", "azure", "outlook")):
        print("MSMODEL", model)
if "justech.microsoft.mail.config" in env:
    print("MSCFG_COUNT", env["justech.microsoft.mail.config"].sudo().search_count([]))
    for rec in env["justech.microsoft.mail.config"].sudo().search([]):
        keys = [
            f
            for f in rec._fields
            if any(
                x in f
                for x in (
                    "enable",
                    "active",
                    "mailbox",
                    "company",
                    "tenant",
                    "from",
                    "domain",
                    "state",
                )
            )
        ]
        vals = {}
        for f in keys[:25]:
            v = getattr(rec, f)
            if any(x in f for x in ("secret", "password", "token", "cert", "key")):
                vals[f] = "SET" if v else "EMPTY"
            else:
                vals[f] = v
        print("MSCFG", rec.id, vals)

print("EXTRA_DONE")
