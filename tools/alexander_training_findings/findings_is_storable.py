# ruff: noqa
v = env.ref("stock.view_template_property_form")
arch = v.arch_db or ""
print("is_storable" in arch, "tracking" in arch)
print(arch[:800])
