from datetime import timedelta

from odoo import api, fields, models


class JustechAuditRetention(models.Model):
    _name = "justech.audit.retention"
    _description = "Justech Audit Retention Policy"
    _order = "id"

    name = fields.Char(required=True, default="Retención de auditoría")
    active = fields.Boolean(default=True, index=True)
    retention_days = fields.Integer(
        string="Días de retención",
        default=365,
        required=True,
        help="Registros más antiguos serán eliminados por el cron de limpieza.",
    )
    batch_size = fields.Integer(
        string="Tamaño de lote",
        default=5000,
        required=True,
    )
    last_run_at = fields.Datetime(readonly=True)
    last_purged_count = fields.Integer(readonly=True)
    notes = fields.Text()

    @api.model
    def _cron_purge_old_logs(self):
        retention = self.search([("active", "=", True)], limit=1)
        if not retention or retention.retention_days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=retention.retention_days)
        purged = self.env["justech.audit.log"]._purge_before(
            cutoff, batch_size=retention.batch_size
        )
        retention.write(
            {
                "last_run_at": fields.Datetime.now(),
                "last_purged_count": purged,
            }
        )
        return purged

    def action_run_now(self):
        self.ensure_one()
        return self._cron_purge_old_logs()
