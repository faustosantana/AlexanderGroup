# -*- coding: utf-8 -*-
assert env.cr.dbname == "doralex_prod"
from odoo.modules.module import get_module_path, get_manifest

print("GET_MODULE_PATH", get_module_path("justech_sale_purchase_trace"))
print(
    "GET_MANIFEST_VERSION", get_manifest("justech_sale_purchase_trace").get("version")
)
m = (
    env["ir.module.module"]
    .sudo()
    .search([("name", "=", "justech_sale_purchase_trace")], limit=1)
)
print("latest_version", m.latest_version)
print("installed_version", m.installed_version)
print("state", m.state)
print(
    "FIELDS",
    {
        f: m._fields[f].string
        for f in ("latest_version", "installed_version")
        if f in m._fields
    },
)
import odoo.addons.justech_sale_purchase_trace as packed

print("PACKED_FILE", getattr(packed, "__file__", None))
print("PACKED_PATH", list(getattr(packed, "__path__", [])))
print("TRACE_PATH_DONE")
