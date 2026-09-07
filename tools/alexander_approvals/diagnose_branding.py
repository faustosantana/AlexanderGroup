"""Diagnose approval menus, module version, and Justech settings labels."""
import json

Mod = env["ir.module.module"].sudo()
ux = Mod.search([("name", "=", "justech_alexander_ux")], limit=1)
flow = Mod.search([("name", "=", "justech_approval_flow")], limit=1)

root = env.ref("justech_approval_flow.menu_justech_approval_root", raise_if_not_found=False)
settings = env.ref("base.menu_administration", raise_if_not_found=False)
children = env["ir.ui.menu"].search([("parent_id", "=", root.id)]) if root else env["ir.ui.menu"]
roots = env["ir.ui.menu"].search([("parent_id", "=", False), ("active", "=", True)])
approval_roots = [
    {"id": m.id, "name": m.name, "xmlid": m.get_external_id().get(m.id)}
    for m in roots
    if "aprobacion" in (m.name or "").lower() or "approval" in (m.name or "").lower()
]

justech_menus = [
    m.complete_name
    for m in env["ir.ui.menu"].search([("active", "=", True)])
    if "justech" in (m.name or "").lower()
]

view = env.ref(
    "justech_alexander_ux.res_config_settings_view_form_approval_branding",
    raise_if_not_found=False,
)
vendor_view = env.ref(
    "justech_approval_flow.res_config_settings_view_form_justech_approval",
    raise_if_not_found=False,
)
base_view = env.ref("base.res_config_settings_view_form")
combined = ""
try:
    combined = str(base_view.get_combined_arch())
except Exception as exc:  # noqa: BLE001
    combined = "ERROR:" + str(exc)[:240]

langs = [lang.code for lang in env["res.lang"].search([])]
flow_names = {}
if flow:
    for code in langs + ["en_US", False]:
        rec = flow.with_context(lang=code) if code else flow
        flow_names[str(code)] = rec.shortdesc

hits = []
for needle in ("Aprobaciones Justech", "Justech Approval", "justech.do", "justgroup.app"):
    if needle.lower() in combined.lower():
        hits.append(needle)

report = {
    "ux_version": ux.latest_version if ux else None,
    "ux_state": ux.state if ux else None,
    "flow_version": flow.latest_version if flow else None,
    "flow_shortdesc": flow_names,
    "root_parent": root.parent_id.name if root and root.parent_id else None,
    "root_active": bool(root and root.active),
    "root_name": root.name if root else None,
    "children": [{"name": c.name, "seq": c.sequence, "active": c.active} for c in children],
    "approval_roots": approval_roots,
    "justech_menus": justech_menus,
    "branding_view": bool(view),
    "branding_active": bool(view and view.active),
    "vendor_string": (vendor_view.arch_db or "")[:400] if vendor_view else None,
    "combined_justech_hits": hits,
    "combined_has_flujo": "Flujo de Aprobaciones" in combined,
    "combined_has_justech_app": "Aprobaciones Justech" in combined,
    "mail_servers": env["ir.mail_server"].sudo().search_count([]),
    "posted_invoices": env["account.move"].sudo().search_count(
        [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
    ),
}
print(json.dumps(report, indent=2, default=str))
