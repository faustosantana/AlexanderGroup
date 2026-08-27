from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env["ir.module.module"].search(
        [("name", "=", "justech_global_audit_log")], limit=1
    )
    if module:
        module.write({"application": False})

    menu = env.ref("justech_global_audit_log.menu_justech_global_audit_root", raise_if_not_found=False)
    if menu:
        settings = env.ref("base.menu_administration")
        menu.write(
            {
                "parent_id": settings.id,
                "web_icon": False,
                "action": False,
            }
        )

    config_menu = env.ref(
        "justech_global_audit_log.menu_justech_audit_config", raise_if_not_found=False
    )
    if config_menu:
        config_menu.unlink()
