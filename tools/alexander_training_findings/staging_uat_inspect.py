print("DB", env.cr.dbname)
SOL = env["sale.order.line"]
print("SOL tax fields", [f for f in SOL._fields if "tax" in f])
print("users group fields", [f for f in env["res.users"]._fields if "group" in f])
print("groups user fields", [f for f in env["res.groups"]._fields if "user" in f or f == "users"])
print("compose fields", [f for f in env["mail.compose.message"]._fields if "sign" in f or "from" in f or "reply" in f or "company" in f])
print("NCF ranges")
if "justech.do.ncf.range" in env:
    for r in env["justech.do.ncf.range"].sudo().search([], limit=30):
        print(
            r.id,
            getattr(r, "company_id", False) and r.company_id.id,
            r.display_name,
            {f: r[f] for f in r._fields if f in ("active", "state", "document_type", "prefix", "ncf_type", "type")},
        )
if "l10n_latam.document.type" in env:
    docs = env["l10n_latam.document.type"].sudo().search([("code", "in", ["01", "B01", "31"])], limit=10)
    print("latam docs", [(d.id, d.name, getattr(d, "doc_code_prefix", None), getattr(d, "code", None)) for d in docs])
print("taxes 461-466")
for t in env["account.tax"].sudo().browse([461, 462, 463, 464, 465, 466]):
    if t.exists():
        print(t.id, t.company_id.id, t.name, t.amount, t.type_tax_use, t.price_include)
print("H01 so leftovers", env["sale.order"].search([("order_line.product_id.default_code", "=", "DXUAT-ITBIS16")]).mapped("name"))
