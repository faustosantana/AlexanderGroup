def post_init_hook(env):
    env["res.company"].sudo()._dx_bootstrap_doralex()
    env["ir.ui.menu"].sudo()._dx_apply_spanish_menu_overrides()
