def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_base.models.res_users import (
        _dx_grant_geilin_full_accounting,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _dx_grant_geilin_full_accounting(env)
