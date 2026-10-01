def post_init_hook(env):
    env["res.company"].sudo()._dx_bootstrap_doralex()
    env["ir.ui.menu"].sudo()._dx_apply_spanish_menu_overrides()
    env["ir.ui.menu"].sudo()._dx_apply_spanish_crm_records()
    from .models.res_groups import _dx_grant_internal_product_create
    from .models.res_users import _dx_apply_spanish_ui_language

    _dx_grant_internal_product_create(env)
    _dx_apply_spanish_ui_language(env)
    env[
        "justech.alexander.multicompany.tax.service"
    ]._dx_apply_safe_product_tax_cleanup()
    env["res.partner.bank"]._dx_trust_company_owned_banks()
