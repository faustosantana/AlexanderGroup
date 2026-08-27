from odoo import api, fields, models


class JustechAuditDashboard(models.TransientModel):
    _name = "justech.audit.dashboard"
    _description = "Panel de investigación"

    total_logs = fields.Integer(compute="_compute_stats", string="Total de registros")
    logs_today = fields.Integer(compute="_compute_stats", string="Cambios hoy")
    unlinks_today = fields.Integer(compute="_compute_stats", string="Eliminaciones hoy")
    writes_today = fields.Integer(compute="_compute_stats", string="Modificaciones hoy")
    active_rules = fields.Integer(compute="_compute_stats", string="Reglas activas")
    table_size_mb = fields.Float(compute="_compute_stats", digits=(16, 3), string="Tamaño tabla (MB)")
    top_user_name = fields.Char(compute="_compute_stats", string="Usuario más activo hoy")
    top_user_count = fields.Integer(compute="_compute_stats")
    last_unlink_summary = fields.Char(compute="_compute_stats", string="Última eliminación")
    after_hours_count = fields.Integer(compute="_compute_stats", string="Cambios fuera de horario hoy")
    bulk_change_count = fields.Integer(compute="_compute_stats", string="Cambios masivos hoy")
    forensic_notice = fields.Html(compute="_compute_stats", sanitize=False)

    @api.depends_context("uid")
    def _compute_stats(self):
        Log = self.env["justech.audit.log"].sudo()
        today = fields.Date.context_today(self)
        today_start = fields.Datetime.to_datetime(today)
        self.env.cr.execute("SELECT pg_total_relation_size(%s)", (Log._table,))
        table_bytes = self.env.cr.fetchone()[0] or 0

        for dashboard in self:
            dashboard.total_logs = Log.search_count([])
            dashboard.logs_today = Log.search_count([("change_date", ">=", today_start)])
            dashboard.unlinks_today = Log.search_count(
                [("change_date", ">=", today_start), ("operation_type", "=", "unlink")]
            )
            dashboard.writes_today = Log.search_count(
                [("change_date", ">=", today_start), ("operation_type", "=", "write")]
            )
            dashboard.active_rules = self.env["justech.audit.rule"].search_count(
                [("active", "=", True)]
            )
            dashboard.table_size_mb = table_bytes / (1024 * 1024)

            user_groups = Log.read_group(
                [("change_date", ">=", today_start)],
                ["user_id"],
                ["user_id"],
                orderby="user_id_count desc",
                limit=1,
            )
            if user_groups and user_groups[0].get("user_id"):
                dashboard.top_user_name = user_groups[0]["user_id"][1]
                dashboard.top_user_count = user_groups[0].get("user_id_count") or user_groups[0].get(
                    "__count", 0
                )
            else:
                dashboard.top_user_name = False
                dashboard.top_user_count = 0

            last_unlink = Log.search([("operation_type", "=", "unlink")], limit=1, order="change_date desc")
            dashboard.last_unlink_summary = last_unlink.human_summary if last_unlink else "—"

            after_hours = Log.search([("change_date", ">=", today_start)])
            dashboard.after_hours_count = len(
                [
                    log
                    for log in after_hours
                    if log.change_date
                    and (log.change_date.hour < 7 or log.change_date.hour >= 19)
                ]
            )

            bulk_users = Log.read_group(
                [("change_date", ">=", today_start)],
                ["user_id"],
                ["user_id"],
            )
            dashboard.bulk_change_count = sum(
                count
                for group in bulk_users
                for count in [group.get("user_id_count") or group.get("__count", 0)]
                if count > 20
            )

            dashboard.forensic_notice = (
                "<p><strong>Panel de investigación:</strong> use el histórico para responder "
                "quién cambió qué, cuándo y desde dónde.</p>"
            )

    def action_open_logs(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Histórico de Cambios",
            "res_model": "justech.audit.log",
            "view_mode": "list,form",
            "context": {"search_default_filter_last_7_days": 1},
        }

    def action_open_unlinks_today(self):
        today = fields.Date.context_today(self)
        return {
            "type": "ir.actions.act_window",
            "name": "Eliminaciones hoy",
            "res_model": "justech.audit.log",
            "view_mode": "list,form",
            "domain": [
                ("change_date", ">=", fields.Datetime.to_datetime(today)),
                ("operation_type", "=", "unlink"),
            ],
        }

    def action_open_changes_today(self):
        today = fields.Date.context_today(self)
        return {
            "type": "ir.actions.act_window",
            "name": "Cambios hoy",
            "res_model": "justech.audit.log",
            "view_mode": "list,form",
            "domain": [("change_date", ">=", fields.Datetime.to_datetime(today))],
        }

    def action_open_rules(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Reglas de auditoría",
            "res_model": "justech.audit.rule",
            "view_mode": "list,form",
            "context": {"search_default_filter_active": 1},
        }

    def action_open_retention(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Retención",
            "res_model": "justech.audit.retention",
            "view_mode": "list,form",
        }

    def action_run_retention(self):
        retention = self.env["justech.audit.retention"].search([("active", "=", True)], limit=1)
        if retention:
            retention.action_run_now()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Retención",
                "message": "Limpieza ejecutada." if retention else "No hay retención activa.",
                "type": "success" if retention else "warning",
                "sticky": False,
            },
        }

    def action_export_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Exportar auditoría",
            "res_model": "justech.audit.export.wizard",
            "view_mode": "form",
            "target": "new",
        }
