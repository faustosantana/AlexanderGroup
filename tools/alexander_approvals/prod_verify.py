"""Read-only production verification after overlay 19.0.1.3.3."""
import json

Mod = env["ir.module.module"].sudo()
ux = Mod.search([("name", "=", "justech_alexander_ux")], limit=1)
root = env.ref("justech_approval_flow.menu_justech_approval_root")
settings = env.ref("base.menu_administration")
children = env["ir.ui.menu"].search([("parent_id", "=", root.id)], order="sequence,id")
roots = env["ir.ui.menu"].search([("parent_id", "=", False), ("active", "=", True)])
approval_roots = [
    m.name
    for m in roots
    if "aprobacion" in (m.name or "").lower() or "approval" in (m.name or "").lower()
]
combined = str(env.ref("base.res_config_settings_view_form").get_combined_arch())
justech = []
for menu in env["ir.ui.menu"].search([("active", "=", True)]):
    if "justech" in (menu.name or "").lower():
        justech.append(menu.complete_name)
for needle in ("Aprobaciones Justech", "Justech Approval", "justech.do", "justgroup.app"):
    if needle.lower() in combined.lower():
        justech.append("settings:" + needle)
alex = env["res.users"].sudo().search(
    [("login", "=", "alexander.pina@inversionesdoralex.com")], limit=1
)
manager = env.ref("justech_approval_flow.group_manager")
approver = env.ref("justech_approval_flow.group_approver")
self_approve = env.ref("justech_approval_flow.group_self_approve")
ops = {}
for login in (
    "luis.aquino@inversionesdoralex.com",
    "janny.montero@inversionesdoralex.com",
    "elianny.sanchez@inversionesdoralex.com",
    "leopordo.jimenez@inversionesdoralex.com",
    "geilin.rosario@inversionesdoralex.com",
):
    user = env["res.users"].sudo().search([("login", "=", login)], limit=1)
    ops[login] = {
        "manager": bool(user and manager in user.group_ids),
        "approver": bool(user and approver in user.group_ids),
        "self_approve": bool(user and self_approve in user.group_ids),
        "companies": user.company_ids.mapped("name") if user else [],
    }
list_view = env.ref(
    "justech_alexander_ux.view_justech_approval_request_list_alexander",
    raise_if_not_found=False,
)
print(
    json.dumps(
        {
            "ux_version": ux.latest_version if ux else None,
            "top_level": not bool(root.parent_id) and root.active,
            "parent": root.parent_id.name if root.parent_id else None,
            "children": [c.name for c in children],
            "approval_roots": approval_roots,
            "settings_flujo": "Flujo de Aprobaciones" in combined,
            "settings_justech_app": "Aprobaciones Justech" in combined,
            "settings_inbox": "action_justech_approval_pending" in combined,
            "justech_visible": justech,
            "alexander_admin": bool(alex and manager in alex.group_ids),
            "alexander_approver": bool(alex and approver in alex.group_ids),
            "ops": ops,
            "posted_invoices": env["account.move"].sudo().search_count(
                [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
            ),
            "mail_servers": env["ir.mail_server"].sudo().search_count([]),
            "list_view": bool(list_view),
        },
        indent=2,
        default=str,
    )
)
