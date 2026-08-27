from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_global_audit_log.hooks import (
        _ensure_default_rules,
        _grant_audit_access_to_admins,
    )

    _ensure_default_rules(env)
    _grant_audit_access_to_admins(env)
