# Read-only go-live dump. No writes. No mail / DGII / e-CF.
env = env  # noqa: F821
import json

cr = env.cr
ctx = {
    "active_test": False,
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
}
T = env["product.template"].sudo().with_context(**ctx)
P = env["product.product"].sudo().with_context(**ctx)

# --- Odoo 19 product type fields ---
meta = T.fields_get(
    ["type", "is_storable", "sale_ok", "purchase_ok", "tracking", "invoice_policy"]
)
field_report = {
    name: {
        "type": m.get("type"),
        "string": m.get("string"),
        "selection": m.get("selection"),
        "store": m.get("store"),
        "help": (m.get("help") or "")[:240],
    }
    for name, m in meta.items()
}


def counts(model):
    recs = model.search([])
    active = recs.filtered("active")
    return {
        "total": len(recs),
        "active": len(active),
        "archived": len(recs) - len(active),
    }


tmpl = counts(T)
prod = counts(P)
shared_t = T.search([("company_id", "=", False)])
pin_t = T.search([("company_id", "=", 9)])
dx_t = T.search(
    [
        "|",
        "|",
        ("name", "ilike", "DXQA"),
        ("name", "ilike", "DX TEST"),
        ("name", "ilike", "DX-QA"),
    ]
)
catalog_t = T.search(
    [
        ("active", "=", True),
        ("name", "not ilike", "DXQA"),
        ("name", "not ilike", "DX TEST"),
        ("name", "not ilike", "DX-QA"),
    ]
)
shared_active = T.search([("active", "=", True), ("company_id", "=", False)])
shared_active_catalog = T.search(
    [
        ("active", "=", True),
        ("company_id", "=", False),
        ("name", "not ilike", "DXQA"),
        ("name", "not ilike", "DX TEST"),
        ("name", "not ilike", "DX-QA"),
    ]
)

type_dist = {}
storable = {"true": 0, "false": 0}
for rec in T.search([("active", "=", True)]):
    type_dist[rec.type] = type_dist.get(rec.type, 0) + 1
    if rec.is_storable:
        storable["true"] += 1
    else:
        storable["false"] += 1

focus = {}
for pid in (21, 138, 168):
    rec = T.browse(pid)
    if rec.exists():
        focus[pid] = {
            "name": rec.name,
            "type": rec.type,
            "is_storable": bool(rec.is_storable),
            "sale_ok": bool(rec.sale_ok),
            "purchase_ok": bool(rec.purchase_ok),
            "active": bool(rec.active),
            "company_id": rec.company_id.id or False,
            "list_price": float(rec.list_price or 0),
        }

# All templates for nature classify (local)
rows = []
for rec in T.search([]):
    name = rec.name or ""
    if isinstance(name, dict):
        name = name.get("es_DO") or name.get("en_US") or str(name)
    rows.append(
        {
            "PRODUCT_ID": rec.id,
            "NAME": name,
            "CURRENT_TYPE": rec.type,
            "CURRENT_SALE_OK": bool(rec.sale_ok),
            "CURRENT_PURCHASE_OK": bool(rec.purchase_ok),
            "IS_STORABLE": bool(rec.is_storable),
            "ACTIVE": bool(rec.active),
            "COMPANY_ID": rec.company_id.id or False,
            "COMPANY": rec.company_id.name or "SHARED",
            "CATEGORY": rec.categ_id.name or "",
            "LIST_PRICE": float(rec.list_price or 0),
        }
    )

# Companies
cos = []
for c in env["res.company"].sudo().browse([8, 9, 10, 11, 12, 13]):
    banks = env["res.partner.bank"].sudo().search([("company_id", "=", c.id)])
    journals = env["account.journal"].sudo().search([("company_id", "=", c.id)])
    taxes = (
        env["account.tax"]
        .sudo()
        .search_count([("company_id", "=", c.id), ("active", "=", True)])
    )
    wh = env["stock.warehouse"].sudo().search([("company_id", "=", c.id)])
    users = (
        env["res.users"]
        .sudo()
        .search([("company_ids", "in", c.id), ("share", "=", False)])
    )
    cos.append(
        {
            "id": c.id,
            "name": c.name,
            "currency": c.currency_id.name,
            "vat": (c.vat or "")[:20],
            "sale_tax": c.account_sale_tax_id.display_name,
            "purchase_tax": c.account_purchase_tax_id.display_name,
            "journals": [(j.code, j.type, j.name) for j in journals],
            "warehouses": [(w.code, w.name) for w in wh],
            "users": [(u.id, u.name, u.login) for u in users],
            "banks": len(banks),
            "taxes_active": taxes,
        }
    )

# Users / groups
GROUP_XML = {
    "SALES": "sales_team.group_sale_salesman",
    "SALES_ALL": "sales_team.group_sale_salesman_all_leads",
    "SALES_MGR": "sales_team.group_sale_manager",
    "PURCHASE": "purchase.group_purchase_user",
    "PURCHASE_MGR": "purchase.group_purchase_manager",
    "INVOICE": "account.group_account_invoice",
    "ACCOUNT_USER": "account.group_account_user",
    "ACCOUNT_MGR": "account.group_account_manager",
    "SETTINGS": "base.group_system",
    "ADMIN": "base.group_erp_manager",
    "STOCK": "stock.group_stock_user",
}
users_out = []
for u in env["res.users"].sudo().search([("share", "=", False)], order="id"):
    flags = {}
    for key, xml in GROUP_XML.items():
        rec = env.ref(xml, raise_if_not_found=False)
        flags[key] = bool(rec and rec in u.groups_id)
    users_out.append(
        {
            "id": u.id,
            "name": u.name,
            "login": u.login,
            "active": bool(u.active),
            "company_id": u.company_id.id,
            "company": u.company_id.name,
            "company_ids": u.company_ids.ids,
            "flags": flags,
        }
    )

# Approvals
approval_out = {}
for xml in (
    "justech_approval_flow.group_approval_user",
    "justech_approval_flow.group_approval_manager",
    "justech_approval_flow.group_approval_admin",
):
    rec = env.ref(xml, raise_if_not_found=False)
    approval_out[xml] = [(u.id, u.name) for u in rec.users] if rec else "MISSING"

# Accounting
unbalanced = 0
cr.execute("""
    SELECT COUNT(*) FROM account_move
    WHERE state = 'posted' AND ABS(amount_total_signed) IS NOT NULL
    """)
posted_moves = cr.fetchone()[0]
cr.execute("""
    SELECT m.id, m.name, m.company_id
    FROM account_move m
    WHERE m.state = 'posted'
      AND ABS((
        SELECT COALESCE(SUM(l.debit - l.credit), 0)
        FROM account_move_line l WHERE l.move_id = m.id
      )) > 0.005
    """)
unbal_rows = cr.fetchall()
unbalanced = len(unbal_rows)

cr.execute("""
    SELECT am.company_id, COALESCE(SUM(aml.amount_residual), 0)
    FROM account_move am
    JOIN account_move_line aml ON aml.move_id = am.id
    WHERE am.move_type IN ('out_invoice', 'out_refund')
      AND am.state = 'posted'
      AND aml.account_id IN (
        SELECT id FROM account_account WHERE account_type = 'asset_receivable'
      )
    GROUP BY 1
    """)
ar_by_co = cr.fetchall()
cr.execute("""
    SELECT COALESCE(SUM(aml.amount_residual), 0)
    FROM account_move am
    JOIN account_move_line aml ON aml.move_id = am.id
    WHERE am.move_type IN ('out_invoice', 'out_refund')
      AND am.state = 'posted'
      AND aml.account_id IN (
        SELECT id FROM account_account WHERE account_type = 'asset_receivable'
      )
    """)
ar_total = cr.fetchone()[0]

# Taxes cross-company
cr.execute("""
    SELECT COUNT(*) FROM account_tax_sale_order_line_rel rel
    JOIN sale_order_line sol ON sol.id = rel.sale_order_line_id
    JOIN sale_order so ON so.id = sol.order_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE tax.company_id IS NOT NULL AND tax.company_id <> so.company_id
      AND so.state IN ('draft', 'sent', 'sale')
    """)
cross_sale = cr.fetchone()[0]
cr.execute("""
    SELECT COUNT(*) FROM account_tax_purchase_order_line_rel rel
    JOIN purchase_order_line pol ON pol.id = rel.purchase_order_line_id
    JOIN purchase_order po ON po.id = pol.order_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE tax.company_id IS NOT NULL AND tax.company_id <> po.company_id
      AND po.state IN ('draft', 'sent', 'to approve', 'purchase')
    """)
cross_po = cr.fetchone()[0]
cr.execute("""
    SELECT COUNT(*) FROM account_move_line_account_tax_rel rel
    JOIN account_move_line aml ON aml.id = rel.account_move_line_id
    JOIN account_move am ON am.id = aml.move_id
    JOIN account_tax tax ON tax.id = rel.account_tax_id
    WHERE am.state = 'draft'
      AND am.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
      AND tax.company_id IS NOT NULL AND tax.company_id <> am.company_id
    """)
cross_inv = cr.fetchone()[0]

# NCF ranges
ncf_rows = []
if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].sudo().search([]):
        ncf_rows.append(
            {
                "id": r.id,
                "company": r.company_id.name,
                "company_id": r.company_id.id,
                "type": getattr(r, "document_type_id", False)
                and r.document_type_id.display_name
                or getattr(r, "l10n_latam_document_type_id", False)
                and r.l10n_latam_document_type_id.display_name
                or "",
                "state": r.state if "state" in r._fields else "",
                "prefix": r.prefix if "prefix" in r._fields else "",
                "from": r.number_from if "number_from" in r._fields else "",
                "to": r.number_to if "number_to" in r._fields else "",
                "next": r.number_next if "number_next" in r._fields else "",
                "date_to": str(r.date_to) if "date_to" in r._fields else "",
            }
        )

# Modules
mods = []
for m in (
    env["ir.module.module"].sudo().search([("state", "=", "installed")], order="name")
):
    if (
        m.name.startswith(
            ("justech_", "l10n_do", "multi_invoice", "bi_convert", "studio")
        )
        or "alexander" in m.name
    ):
        mods.append({"name": m.name, "version": m.latest_version})

# QWeb
qweb = env["ir.ui.view"].sudo().search_count([("type", "=", "qweb")])

# Sales / purchase / invoice counts
so_c = {
    "draft": env["sale.order"].sudo().search_count([("state", "=", "draft")]),
    "sale": env["sale.order"].sudo().search_count([("state", "=", "sale")]),
}
po_c = {
    "draft": env["purchase.order"].sudo().search_count([("state", "=", "draft")]),
    "purchase": env["purchase.order"].sudo().search_count([("state", "=", "purchase")]),
}
inv_c = {
    "draft": env["account.move"]
    .sudo()
    .search_count(
        [("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "draft")]
    ),
    "posted": env["account.move"]
    .sudo()
    .search_count(
        [("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted")]
    ),
}

# B1300000016
miss_pdf = []
move = env["account.move"].sudo().search([("name", "ilike", "B1300000016")], limit=5)
for m in move:
    atts = (
        env["ir.attachment"]
        .sudo()
        .search_count([("res_model", "=", "account.move"), ("res_id", "=", m.id)])
    )
    miss_pdf.append(
        {
            "id": m.id,
            "name": m.name,
            "ncf": getattr(m, "l10n_latam_document_number", ""),
            "atts": atts,
        }
    )

out = {
    "PRODUCT_TYPE_FIELDS": field_report,
    "PRODUCT_TEMPLATE": tmpl,
    "PRODUCT_PRODUCT": prod,
    "SHARED_TEMPLATES_ALL": len(shared_t),
    "SHARED_TEMPLATES_ACTIVE": len(shared_active),
    "SHARED_TEMPLATES_ACTIVE_CATALOG": len(shared_active_catalog),
    "PINARIA_ONLY_TEMPLATES": len(pin_t),
    "PINARIA_ONLY_ACTIVE": len(pin_t.filtered("active")),
    "DX_TEST_TEMPLATES": len(dx_t),
    "CATALOG_ACTIVE_NO_DX": len(catalog_t),
    "TYPE_DISTRIBUTION_ACTIVE": type_dist,
    "IS_STORABLE_ACTIVE": storable,
    "FOCUS": focus,
    "TEMPLATES": rows,
    "COMPANIES": cos,
    "USERS": users_out,
    "APPROVAL_GROUPS": approval_out,
    "POSTED_MOVES": posted_moves,
    "UNBALANCED_MOVES": unbalanced,
    "UNBALANCED_IDS": unbal_rows[:20],
    "AR_BY_COMPANY": ar_by_co,
    "AR_TOTAL": float(ar_total or 0),
    "CROSS_SALE": cross_sale,
    "CROSS_PO": cross_po,
    "CROSS_INV": cross_inv,
    "NCF": ncf_rows,
    "MODULES": mods,
    "QWEB_TOTAL": qweb,
    "SALE_COUNTS": so_c,
    "PO_COUNTS": po_c,
    "INV_COUNTS": inv_c,
    "B13_0016": miss_pdf,
    "ODOO_VERSION": env["ir.module.module"]
    .sudo()
    .search([("name", "=", "base")], limit=1)
    .latest_version,
}
path = "/tmp/golive_dump.json"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, default=str)
print(
    "WROTE",
    path,
    "templates",
    len(rows),
    "catalog_active_no_dx",
    len(catalog_t),
    "shared_active",
    len(shared_active),
)
print("FOCUS", focus)
print(
    "AR_TOTAL",
    ar_total,
    "UNBALANCED",
    unbalanced,
    "CROSS",
    cross_sale,
    cross_po,
    cross_inv,
)
