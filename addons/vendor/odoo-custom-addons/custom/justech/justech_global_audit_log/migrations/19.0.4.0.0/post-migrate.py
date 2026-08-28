from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_global_audit_log.hooks import (
        _backfill_forensic_logs,
        _load_sale_audit_actions,
    )

    _backfill_forensic_logs(env)
    _load_sale_audit_actions(env)
