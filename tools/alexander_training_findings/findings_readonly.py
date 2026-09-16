# ruff: noqa
"""READ-ONLY findings dump. No writes."""

import json

ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
sudo = lambda m: env[m].sudo().with_context(**ctx)

# --- H01 taxes ---
taxes = []
Tax = sudo("account.tax")
for t in Tax.search(
    [("type_tax_use", "in", ("sale", "purchase", "none"))],
    order="company_id, amount, name",
):
    taxes.append(
        {
            "id": t.id,
            "name": t.name,
            "amount": t.amount,
            "amount_type": t.amount_type,
            "type_tax_use": t.type_tax_use,
            "price_include": t.price_include,
            "company": t.company_id.name,
            "company_id": t.company_id.id,
            "active": t.active,
            "description": (
                (t.description or "")[:80] if "description" in t._fields else ""
            ),
            "repartition_sale": [
                {
                    "factor_percent": l.factor_percent,
                    "account": l.account_id.code if l.account_id else "",
                    "repartition_type": l.repartition_type,
                }
                for l in t.invoice_repartition_line_ids
            ],
        }
    )

itbis16 = [t for t in taxes if abs((t["amount"] or 0) - 16.0) < 0.01]
itbis18 = [t for t in taxes if abs((t["amount"] or 0) - 18.0) < 0.01]

# product tax usage
prod_tax = []
env.cr.execute("""
    SELECT t.company_id, t.name, t.amount, count(*)
    FROM product_taxes_rel r
    JOIN account_tax t ON t.id = r.tax_id
    GROUP BY t.company_id, t.name, t.amount
    ORDER BY 4 DESC
    LIMIT 40
    """)
prod_tax = [
    {"company_id": r[0], "name": r[1], "amount": r[2], "products": r[3]}
    for r in env.cr.fetchall()
]

# --- H02 descriptions ---
desc_fields = [
    f
    for f in ("name", "description_sale", "description", "description_picking")
    if f in sudo("product.template")._fields
]
line_fields = [
    f
    for f in ("name", "product_id", "product_template_id")
    if f in sudo("sale.order.line")._fields
]
sample_mismatch = []
try:
    env.cr.execute("""
        SELECT sol.id, so.name, pt.default_code, pt.name, sol.name
        FROM sale_order_line sol
        JOIN sale_order so ON so.id = sol.order_id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE sol.display_type IS NULL
          AND sol.name IS NOT NULL
        ORDER BY sol.id DESC
        LIMIT 25
        """)
    sample_mismatch = [
        {
            "line": r[0],
            "so": r[1],
            "code": r[2],
            "tmpl": r[3],
            "line_name": (r[4] or "")[:160],
        }
        for r in env.cr.fetchall()
    ]
except Exception as exc:
    sample_mismatch = [{"error": str(exc)}]

# --- H03/H08 reports ---
reports = []
for r in sudo("ir.actions.report").search(
    [("model", "in", ("sale.order", "account.move", "stock.picking"))],
    order="model, name",
):
    reports.append(
        {
            "id": r.id,
            "name": r.name,
            "report_name": r.report_name,
            "model": r.model,
            "report_type": r.report_type,
            "xmlid": r.get_external_id().get(r.id),
        }
    )

# --- H04 sale line view fields ---
sol_fields = sorted(sudo("sale.order.line")._fields)
custom_sol = [f for f in sol_fields if f.startswith(("justech", "x_"))]

# --- H05 tracking ---
pt = sudo("product.template")
tracking_fields = [
    f
    for f in ("type", "is_storable", "tracking", "detailed_type", "use_expiration_date")
    if f in pt._fields
]
tracking_sample = []
for p in (
    pt.search([("is_storable", "=", True)], limit=8)
    if "is_storable" in pt._fields
    else pt.search([("type", "=", "product")], limit=8)
):
    tracking_sample.append(
        {
            "id": p.id,
            "name": p.display_name,
            "type": p.type if "type" in p._fields else None,
            "is_storable": p.is_storable if "is_storable" in p._fields else None,
            "tracking": p.tracking if "tracking" in p._fields else None,
        }
    )

# --- H06 CRM stages ---
stages = []
if "crm.stage" in env:
    for s in sudo("crm.stage").search([]):
        stages.append(
            {
                "id": s.id,
                "name": s.name,
                "team": (
                    ", ".join(s.team_ids.mapped("name"))
                    if "team_ids" in s._fields and s.team_ids
                    else ""
                ),
                "sequence": s.sequence,
                "fold": s.fold,
            }
        )
langs = [
    {"code": l.code, "name": l.name, "active": l.active}
    for l in sudo("res.lang").search([])
]
crm_teams = []
if "crm.team" in env:
    crm_teams = [{"id": t.id, "name": t.name} for t in sudo("crm.team").search([])]

# --- H07/10 groups ---
interesting = []
for g in sudo("res.groups").search([]):
    xmlid = g.get_external_id().get(g.id) or ""
    name = (g.name or "") + " " + xmlid
    if any(
        k in name.lower()
        for k in (
            "recuper",
            "recovery",
            "account",
            "invoice",
            "cancel",
            "advisor",
            "manager",
            "accountant",
            "billing",
        )
    ):
        cat = ""
        if "category_id" in g._fields and g.category_id:
            cat = g.category_id.name
        interesting.append(
            {"id": g.id, "name": g.name, "xmlid": xmlid, "category": cat}
        )

# --- H09 DGII ---
dgii = {}
if "dgii.rnc" in env or "l10n_do.rnc" in env:
    model = "dgii.rnc" if "dgii.rnc" in env else "l10n_do.rnc"
    dgii["model"] = model
    try:
        dgii["count"] = sudo(model).search_count([])
    except Exception as exc:
        dgii["count_error"] = str(exc)
else:
    models = [m for m in env.registry if "rnc" in m or "dgii" in m or "padron" in m]
    dgii["candidate_models"] = models[:40]
crons = []
for c in sudo("ir.cron").search([("active", "in", (True, False))]):
    blob = (c.name or "") + " " + (c.model_id.model if c.model_id else "")
    if any(k in blob.lower() for k in ("dgii", "rnc", "padron", "l10n_do")):
        crons.append(
            {
                "id": c.id,
                "name": c.name,
                "active": c.active,
                "model": c.model_id.model if c.model_id else "",
                "interval": f"{c.interval_number} {c.interval_type}",
                "nextcall": str(c.nextcall),
            }
        )
dgii["crons"] = crons

# --- H11 approvals ---
approval = {"models": [m for m in env.registry if "approv" in m]}
if "sale.order" in env:
    so = sudo("sale.order")
    approval["sale_fields"] = [f for f in so._fields if "approv" in f or "justech" in f]
if "approval.request" in env:
    approval["request_count"] = sudo("approval.request").search_count([])
    approval["categories"] = (
        [
            {
                "id": c.id,
                "name": c.name,
                "model": getattr(c, "approval_type", None)
                or getattr(c, "res_model", None),
            }
            for c in sudo("approval.category").search([])
        ]
        if "approval.category" in env
        else []
    )

# --- H12 client_order_ref ---
so_native = [
    f
    for f in sudo("sale.order")._fields
    if any(k in f for k in ("client_order", "origin", "ref", "po_"))
]

# --- H13 payments ---
pay_fields = [
    f
    for f in sudo("account.payment")._fields
    if any(k in f for k in ("withhold", "reten", "l10n_do", "justech"))
]
pay_reports = [
    {
        "name": r.name,
        "report_name": r.report_name,
        "xmlid": r.get_external_id().get(r.id),
    }
    for r in sudo("ir.actions.report").search([("model", "=", "account.payment")])
]

# --- H15 mail ---
mail = {
    "servers": [
        {
            "id": s.id,
            "name": s.name,
            "smtp_host": s.smtp_host,
            "from_filter": s.from_filter,
            "company": (
                s.company_id.name if "company_id" in s._fields and s.company_id else ""
            ),
        }
        for s in sudo("ir.mail_server").search([])
    ],
    "aliases": (
        [
            {
                "id": a.id,
                "alias": a.alias_name,
                "model": a.alias_model_id.model if a.alias_model_id else "",
            }
            for a in sudo("mail.alias").search([])
        ]
        if "mail.alias" in env
        else []
    ),
}
if "fetchmail.server" in env:
    mail["fetchmail"] = [
        {
            "id": f.id,
            "name": f.name,
            "server": f.server,
            "state": f.state,
            "active": f.active,
        }
        for f in sudo("fetchmail.server").search([])
    ]
params = {
    p.key: p.value
    for p in sudo("ir.config_parameter").search(
        [
            (
                "key",
                "in",
                (
                    "mail.catchall.alias",
                    "mail.catchall.domain",
                    "mail.bounce.alias",
                    "mail.default.from",
                    "mail.default.from_filter",
                ),
            )
        ]
    )
}
mail["params"] = params
failed = sudo("mail.mail").search_count([("state", "=", "exception")])
mail["failed_mails"] = failed

# --- H16 signatures ---
sigs = []
for u in sudo("res.users").search([("share", "=", False), ("active", "=", True)]):
    sigs.append(
        {
            "login": u.login,
            "company": u.company_id.name,
            "signature": bool(u.signature),
            "sig_preview": (u.signature or "")[:180],
        }
    )

# --- H17 menus / home ---
home_menus = []
for m in sudo("ir.ui.menu").search(
    [
        "|",
        "|",
        ("name", "ilike", "home"),
        ("name", "ilike", "dashboard"),
        ("name", "ilike", "inicio"),
    ]
):
    act = m.action
    home_menus.append(
        {
            "id": m.id,
            "name": m.name,
            "complete": m.complete_name,
            "action": f"{act._name},{act.id}" if act else "",
            "xmlid": m.get_external_id().get(m.id),
        }
    )

print(
    json.dumps(
        {
            "DATABASE": env.cr.dbname,
            "H01_ITBIS16": itbis16,
            "H01_ITBIS18_COUNT": len(itbis18),
            "H01_TAXES": taxes,
            "H01_PRODUCT_TAX_USAGE": prod_tax,
            "H02_PRODUCT_FIELDS": desc_fields,
            "H02_LINE_FIELDS": line_fields,
            "H02_SAMPLE_LINES": sample_mismatch,
            "H03_H08_H14_REPORTS": reports,
            "H04_CUSTOM_SOL_FIELDS": custom_sol,
            "H05_TRACKING_FIELDS": tracking_fields,
            "H05_SAMPLE": tracking_sample,
            "H06_STAGES": stages,
            "H06_LANGS": langs,
            "H06_TEAMS": crm_teams,
            "H07_GROUPS": interesting,
            "H09_DGII": dgii,
            "H11_APPROVAL": approval,
            "H12_SO_REF_FIELDS": so_native,
            "H13_PAYMENT_FIELDS": pay_fields,
            "H13_PAYMENT_REPORTS": pay_reports,
            "H15_MAIL": mail,
            "H16_SIGNATURES": sigs,
            "H17_HOME_MENUS": home_menus,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
