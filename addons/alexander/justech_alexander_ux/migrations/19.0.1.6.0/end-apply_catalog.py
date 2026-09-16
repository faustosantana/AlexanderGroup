def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_ux.hooks import (
        _apply_catalog,
        _apply_menu_names,
        _hide_fiscal_leftovers,
        apply_approval_overlay,
        apply_ecf_operational_state,
        apply_padron_disabled,
        apply_withholding_catalog,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_catalog(env)
    _apply_menu_names(env)
    apply_ecf_operational_state(env, enabled=False)
    _hide_fiscal_leftovers(env)
    apply_approval_overlay(env)
    apply_padron_disabled(env)
    apply_withholding_catalog(env)
