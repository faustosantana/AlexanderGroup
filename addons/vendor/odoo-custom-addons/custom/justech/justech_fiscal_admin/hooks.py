# -*- coding: utf-8 -*-
"""Post-instalación: roles fiscales y singleton Centro Fiscal."""


def post_init_hook(env):
    _ensure_role_implications(env)
    _ensure_singleton_centers(env)


def _ensure_role_implications(env):
    admin_fiscal = env.ref(
        "justech_fiscal_admin.group_justech_fiscal_admin_manager",
        raise_if_not_found=False,
    )
    fiscal_user = env.ref(
        "justech_l10n_do_base.group_justech_do_fiscal_user",
        raise_if_not_found=False,
    )
    officer = env.ref(
        "justech_l10n_do_base.group_justech_do_fiscal_manager",
        raise_if_not_found=False,
    )
    system = env.ref("base.group_system", raise_if_not_found=False)
    account_mgr = env.ref("account.group_account_manager", raise_if_not_found=False)
    account_user = env.ref("account.group_account_user", raise_if_not_found=False)

    if system and admin_fiscal and admin_fiscal not in system.implied_ids:
        system.write({"implied_ids": [(4, admin_fiscal.id)]})
    # SoD: quitar herencias incorrectas
    if account_mgr and admin_fiscal and admin_fiscal in account_mgr.implied_ids:
        account_mgr.write({"implied_ids": [(3, admin_fiscal.id)]})
    if account_mgr and fiscal_user and fiscal_user in account_mgr.implied_ids:
        account_mgr.write({"implied_ids": [(3, fiscal_user.id)]})
    if account_user and fiscal_user and fiscal_user in account_user.implied_ids:
        account_user.write({"implied_ids": [(3, fiscal_user.id)]})
    if officer and admin_fiscal and admin_fiscal in officer.implied_ids:
        officer.write({"implied_ids": [(3, admin_fiscal.id)]})

    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if admin and admin_fiscal and admin_fiscal.id not in admin.group_ids.ids:
        admin.write({"group_ids": [(4, admin_fiscal.id)]})


def _ensure_singleton_centers(env):
    Center = env["justech.fiscal.admin.center"].sudo()
    for company in env["res.company"].sudo().search([]):
        centers = Center.search([("company_id", "=", company.id)], order="id")
        if len(centers) > 1:
            centers[1:].unlink()
        elif not centers:
            Center.create({"company_id": company.id})
