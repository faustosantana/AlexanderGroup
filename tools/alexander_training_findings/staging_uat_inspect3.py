arch = env["sale.order"].get_view(view_type="form").get("arch") or ""
if isinstance(arch, bytes):
    arch = arch.decode()
for needle in (
    "justech_qty_purchased",
    "justech_qty_pending_purchase",
    "justech_supply_state",
    "justech_coverage_state",
    "justech_qty_stock_covered",
):
    i = arch.find(needle)
    print("====", needle, i)
    print(arch[max(0, i - 120) : i + 180] if i >= 0 else "ABSENT")

v = env["ir.ui.view"].search([("name", "=", "sale.order.form.dx.hide.trace.cols")], limit=1)
print("inherit exists", bool(v), v.id if v else None, v.active if v else None)
print("inherit arch", v.arch_db if v else None)
print("inherit inherit_id", v.inherit_id.xml_id if v and v.inherit_id else None)

# stock.move required create fields
print("move required-ish", [f for f in ("product_id", "product_uom_qty", "product_uom", "location_id", "description_picking") if f in env["stock.move"]._fields])

# 16% tags
for t in env["account.account.tag"].sudo().search([("name", "in", ["base.16%", "tax.16%", "base.18%", "tax.18%"])]):
    print("tag", t.id, t.name, t.applicability, t.country_id.code)

# withholding catalog sale/customer
Cat = env["justech.do.withholding.catalog"].sudo()
print("catalog count", Cat.search_count([]))
for c in Cat.search([], limit=10):
    print("cat", c.id, c.display_name, {f: c[f] for f in c._fields if f in ("active", "type", "rate", "code", "withholding_type")})
