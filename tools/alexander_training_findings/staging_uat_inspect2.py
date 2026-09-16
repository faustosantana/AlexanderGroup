print("stock.move label fields", [f for f in env["stock.move"]._fields if f in ("name", "description", "description_picking", "origin")])
arch = env["sale.order"].get_view(view_type="form").get("arch") or ""
if isinstance(arch, bytes):
    arch = arch.decode()
idx = arch.find("justech_qty_purchased")
print("arch snippet", arch[max(0, idx - 80) : idx + 200] if idx >= 0 else "MISSING")
print("purchase.group in arch", "purchase.group_purchase_user" in arch)
print("group_purchase" in arch, arch.count("justech_qty"))
# tags 16 vs 18
for name in env["account.account.tag"].sudo().search([("name", "ilike", "16")]).mapped("name"):
    print("tag16", name)
for name in env["account.account.tag"].sudo().search([("name", "ilike", "%ITBIS%")]).mapped("name")[:20]:
    print("tagitbis", name)
# partner 15
p = env["res.partner"].browse(15)
print("partner15", p.name, p.vat, p.company_id.id)
# withholding how
Pay = env["account.payment"]
print("wh line model", Pay._fields.get("justech_withholding_line_ids") and Pay._fields["justech_withholding_line_ids"].comodel_name)
if "justech.payment.withholding.line" in env:
    print("wh line fields", list(env["justech.payment.withholding.line"]._fields)[:40])
for m in sorted(env.registry):
    if "withhold" in m or "justech.wh" in m:
        print("model", m)
# H04 users: sale users
sale_g = env.ref("sales_team.group_sale_salesman")
print("sale group users", sale_g.user_ids.mapped("login")[:15])
print("sale implied", sale_g.implied_ids.mapped("name"))
