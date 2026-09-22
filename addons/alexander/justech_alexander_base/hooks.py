def post_init_hook(env):
    env["res.company"].sudo()._dx_bootstrap_doralex()
    env["ir.ui.menu"].sudo()._dx_apply_spanish_menu_overrides()
    env["ir.ui.menu"].sudo()._dx_apply_spanish_crm_records()
    from .models.res_groups import _dx_grant_internal_product_create

    _dx_grant_internal_product_create(env)
