"""RC6 post: puente de grupos + sync catálogo global (sin tocar históricos de pagos)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Catalog = env.get("justech.do.withholding.catalog")
    if Catalog:
        do_company = env["res.company"].search([]).filtered(
            lambda c: c.country_id and c.country_id.code == "DO"
        )[:1]
        if do_company:
            Catalog.sync_catalog_from_taxes(do_company)

    fiscal_mgr = env.ref(
        "justech_fiscal_admin.group_justech_fiscal_admin_manager", raise_if_not_found=False
    )
    wh_admin = env.ref(
        "justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin",
        raise_if_not_found=False,
    )
    if fiscal_mgr and wh_admin and wh_admin not in fiscal_mgr.implied_ids:
        fiscal_mgr.sudo().write({"implied_ids": [(4, wh_admin.id)]})
    account_mgr = env.ref("account.group_account_manager", raise_if_not_found=False)
    if account_mgr and wh_admin and wh_admin not in account_mgr.implied_ids:
        account_mgr.sudo().write({"implied_ids": [(4, wh_admin.id)]})
