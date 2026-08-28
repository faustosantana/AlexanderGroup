from . import controllers
from . import models
from . import wizards


def post_init_hook(env):
    env["justech.admin.registry.service"].discover_and_sync()
    env["justech.admin.console"].sudo()._ensure_singleton()
    legacy = env.ref("justech_admin.menu_justech_settings_root", raise_if_not_found=False)
    if legacy:
        legacy.write({"active": False})
    # Hide duplicate Settings-side administrative menus if present
    for xid in (
        "justech_fiscal_admin.menu_justech_fiscal_admin_settings",
        "justech_warranty.menu_justech_warranty_config_settings",
    ):
        menu = env.ref(xid, raise_if_not_found=False)
        if menu:
            menu.write({"active": False})
    mgr = env.ref("justech_admin_center.group_justech_admin_center_manager", raise_if_not_found=False)
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if mgr and admin and mgr not in admin.group_ids:
        admin.sudo().write({"group_ids": [(4, mgr.id)]})
