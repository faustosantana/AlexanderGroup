from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_global_audit_log")
class TestJustechAuditRetention(TransactionCase):
    def test_purge_old_logs(self):
        Log = self.env["justech.audit.log"].sudo()
        old_date = fields.Datetime.now() - timedelta(days=400)
        log = Log.create(
            {
                "operation_type": "event",
                "model_name": "res.partner",
                "model_description": "Contact",
                "record_id": 1,
                "record_name": "Old",
                "field_name": "__event__",
                "field_description": "Old",
                "old_value": "",
                "new_value": "{}",
            }
        )
        self.env.cr.execute(
            "UPDATE justech_audit_log SET change_date = %s WHERE id = %s",
            (old_date, log.id),
        )
        purged = Log._purge_before(fields.Datetime.now() - timedelta(days=365), batch_size=100)
        self.assertGreaterEqual(purged, 1)
        self.assertFalse(Log.search([("id", "=", log.id)]))
