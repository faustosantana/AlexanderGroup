def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_ux.hooks import (
        apply_approval_overlay,
        apply_ecf_operational_state,
        apply_padron_disabled,
        apply_withholding_catalog,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    apply_ecf_operational_state(env, enabled=False)
    apply_approval_overlay(env)
    apply_padron_disabled(env)
    apply_withholding_catalog(env)
