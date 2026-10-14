def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_ux.hooks import (
        _apply_catalog,
        hide_margin_control,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_catalog(env)
    hide_margin_control(env)
