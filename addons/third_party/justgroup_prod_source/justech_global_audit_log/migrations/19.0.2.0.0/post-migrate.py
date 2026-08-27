from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_global_audit_log.hooks import _ensure_default_rules

    _ensure_default_rules(env)
