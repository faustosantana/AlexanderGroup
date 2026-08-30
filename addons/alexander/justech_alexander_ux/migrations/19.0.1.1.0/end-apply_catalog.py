def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_ux.hooks import (
        _apply_catalog,
        _apply_menu_names,
        apply_ecf_operational_state,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_catalog(env)
    _apply_menu_names(env)
    apply_ecf_operational_state(env, enabled=False)
