# -*- coding: utf-8 -*-
assert env.cr.dbname == "doralex_prod"
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
print(
    "FETCH_COUNT",
    (
        env["fetchmail.server"].sudo().search_count([])
        if "fetchmail.server" in env
        else None
    ),
)
# microsoft module models
for model in env:
    if "microsoft" in model or "graph" in model or "azure" in model:
        print("MSMODEL", model)
if "justech.microsoft.mail.config" in env:
    for rec in env["justech.microsoft.mail.config"].sudo().search([]):
        print(
            "MSCFG",
            rec.id,
            rec.company_id.id if rec.company_id else None,
            [
                f
                for f in rec._fields
                if "enabled" in f or "active" in f or "mailbox" in f
            ][:20],
        )
# company emails already known; check alias
if "mail.alias.domain" in env:
    for d in env["mail.alias.domain"].sudo().search([]):
        print(
            "ALIASDOM",
            d.name,
            "company=%s"
            % (d.company_id.id if "company_id" in d._fields and d.company_id else None),
        )
print("MAIL_DONE")
