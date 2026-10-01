from odoo import api, models

DX_UI_LANG = "es_DO"
_GEILIN_LOGIN = "geilin.rosario@inversionesdoralex.com"
_GEILIN_ACCOUNTING_XMLIDS = (
    "account.group_account_manager",
    "account.group_validate_bank_account",
)


def _dx_apply_spanish_ui_language(env):
    """Spanish (DO) is the default UI language for every internal user."""
    spanish = (
        env["res.lang"]
        .sudo()
        .with_context(active_test=False)
        .search([("code", "=", DX_UI_LANG)], limit=1)
    )
    if not spanish:
        return
    if not spanish.active:
        spanish.sudo().write({"active": True})
    users = (
        env["res.users"]
        .sudo()
        .with_context(active_test=False)
        .search([("share", "=", False)])
    )
    system = env.ref("base.user_root", raise_if_not_found=False)
    if system:
        users -= system
    partners = users.mapped("partner_id").filtered(lambda p: p.lang != DX_UI_LANG)
    if partners:
        partners.sudo().write({"lang": DX_UI_LANG})
    companies = env["res.company"].sudo().search([]).mapped("partner_id")
    company_fix = companies.filtered(lambda p: p.lang != DX_UI_LANG)
    if company_fix:
        company_fix.sudo().write({"lang": DX_UI_LANG})


def _dx_grant_geilin_full_accounting(env):
    """Accounting Administrator for Geilin only. Not Settings / ERP Manager."""
    user = (
        env["res.users"]
        .sudo()
        .search([("login", "=", _GEILIN_LOGIN), ("share", "=", False)], limit=1)
    )
    if not user:
        return
    commands = []
    for xmlid in _GEILIN_ACCOUNTING_XMLIDS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if not group:
            continue
        if user.has_group(xmlid):
            continue
        commands.append((4, group.id))
    if commands:
        user.write({"group_ids": commands})


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        vals["lang"] = DX_UI_LANG
        return vals

    def _register_hook(self):
        super()._register_hook()
        _dx_apply_spanish_ui_language(self.env)
        _dx_grant_geilin_full_accounting(self.env)


class ResPartnerLangDefault(models.Model):
    _inherit = "res.partner"

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "lang" in fields_list or not fields_list:
            vals["lang"] = DX_UI_LANG
        return vals
