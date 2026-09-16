# -*- coding: utf-8 -*-
"""PROD READ-ONLY mail + flags. Never commit."""

assert env.cr.dbname == "doralex_prod"
print("MAIL2_DB", env.cr.dbname)
Icp = env["ir.config_parameter"].sudo()
for k in (
    "justech_alexander.approval_flow_enabled",
    "justech_alexander.dgii_padron_enabled",
    "justech_alexander.ecf_operational_enabled",
    "justech.approval.public.base.url",
    "web.base.url",
):
    print("PARAM", k, repr(Icp.get_param(k)))
print("SMTP_COUNT", env["ir.mail_server"].sudo().search_count([]))
if "fetchmail.server" in env:
    print("FETCH_COUNT", env["fetchmail.server"].sudo().search_count([]))
if "mail.alias.domain" in env:
    for d in env["mail.alias.domain"].sudo().search([]):
        print("ALIASDOM", d.name)
Partner = env["res.partner"].sudo()
if "justech_do_fiscal_config_state" in Partner._fields:
    print(
        "PARTNER_STATE_COUNTS",
        Partner.read_group(
            [], ["justech_do_fiscal_config_state"], ["justech_do_fiscal_config_state"]
        ),
    )
if "justech.do.rnc.padron.config" in env:
    print(
        "PADRON_CFG_COUNT", env["justech.do.rnc.padron.config"].sudo().search_count([])
    )
    Cfg = env["justech.do.rnc.padron.config"].sudo()
    for rec in Cfg.search([]):
        print(
            "PADRON_CFG",
            rec.id,
            (
                rec.read()[0]
                if False
                else {
                    f: getattr(rec, f)
                    for f in rec._fields
                    if f
                    in (
                        "active",
                        "enabled",
                        "company_id",
                        "auto_update",
                        "block_partners",
                        "block_invoices",
                    )
                    or "enable" in f
                    or "block" in f
                    or "active" in f
                }
            ),
        )
print("=== COMPANY MAIL FIELDS ===")
for c in env["res.company"].sudo().search([]):
    print(
        "MCO",
        c.id,
        c.name,
        "email=%s" % c.email,
        "domain=%s" % getattr(c, "dx_mail_domain", None),
        "mailbox=%s" % getattr(c, "dx_mail_mailbox", None),
        "alias_admin=%s" % getattr(c, "dx_mail_alias_admin", None),
    )
print("=== ITBIS 16/18 ===")
for t in (
    env["account.tax"]
    .sudo()
    .search([("amount", "in", [16.0, 18.0, -16.0, -18.0])], order="company_id,amount")
):
    if t.company_id.id == 1:
        continue
    print(
        "TAX", t.company_id.id, t.name, t.amount, t.type_tax_use, "active=%s" % t.active
    )
print("=== ACCOUNT SAMPLE ===")
acc = env["account.account"].sudo().browse(1897)
print(
    "ACC1897 code=%r type=%s name=%s cos=%s"
    % (acc.code, acc.account_type, acc.name, acc.company_ids.ids)
)
print("ACC_CODE_FIELDS", [f for f in acc._fields if "code" in f])
if "code_store" in acc._fields:
    print("ACC1897 code_store", acc.code_store)
print("MAIL2_DONE")
