from odoo import api, fields, models, tools
from odoo.exceptions import AccessError

from .audit_display import (
    build_changes_html,
    build_display_payload,
    important_field_items,
    label_for_field,
    model_label,
    parse_snapshot,
)


class JustechAuditLog(models.Model):
    _name = "justech.audit.log"
    _description = "Histórico Forense"
    _order = "change_date desc, id desc"
    _rec_name = "human_summary"

    operation_type = fields.Selection(
        selection=[
            ("create", "Creación"),
            ("write", "Modificación"),
            ("unlink", "Eliminación"),
            ("event", "Evento"),
        ],
        required=True,
        index=True,
    )
    model_name = fields.Char(required=True, index=True)
    model_description = fields.Char(string="Tipo de documento", index=True)
    record_id = fields.Integer(required=True, index=True)
    record_name = fields.Char(string="Documento", index=True)
    field_name = fields.Char(string="Campo técnico", index=True)
    field_description = fields.Char(string="Campo", index=True)
    old_value = fields.Text(string="Valor anterior (técnico)")
    new_value = fields.Text(string="Valor nuevo (técnico)")
    human_summary = fields.Char(string="Resumen", index=True)
    action_label = fields.Char(string="Acción", index=True)
    model_label = fields.Char(string="Tipo", index=True)
    document_label = fields.Char(string="Documento", index=True)
    field_label_display = fields.Char(string="Campo", index=True)
    before_display = fields.Char(string="Antes")
    after_display = fields.Char(string="Después")
    result = fields.Char(string="Resultado", default="Registrado")
    search_text = fields.Text(string="Texto de búsqueda", index=True)
    changes_html = fields.Html(string="Qué cambió", compute="_compute_changes_html", sanitize=False)
    user_id = fields.Many2one("res.users", string="Usuario", index=True, ondelete="set null")
    company_id = fields.Many2one("res.company", string="Empresa", index=True, ondelete="set null")
    change_date = fields.Datetime(
        string="Fecha",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    ip_address = fields.Char(string="Dirección IP", index=True)
    user_agent = fields.Char(string="Navegador")
    event_source = fields.Char(string="Origen evento", index=True)
    correlation_id = fields.Char(string="Correlation ID", index=True)

    @api.depends("operation_type", "field_name", "old_value", "new_value", "model_name")
    def _compute_changes_html(self):
        for log in self:
            rows = log._get_change_rows()
            log.changes_html = build_changes_html(rows, operation=log.operation_type)

    def _get_change_rows(self):
        self.ensure_one()
        if self.field_name in ("__create__", "__unlink__"):
            data = parse_snapshot(
                self.new_value if self.field_name == "__create__" else self.old_value
            )
            items = important_field_items(self.model_name, data)
            if self.field_name == "__create__":
                return [(label, "—", value) for label, value in items]
            return [(label, value, "—") for label, value in items]
        if self.operation_type == "write":
            field = self.field_label_display or label_for_field(
                self.field_name, self.field_description
            )
            return [(field, self.before_display or "—", self.after_display or "—")]
        return []

    @api.model
    def _prepare_forensic_fields(self, vals):
        user = self.env["res.users"].browse(vals.get("user_id") or self.env.uid)
        payload = build_display_payload(vals, user_name=user.name)
        vals = dict(vals)
        vals.update(
            {
                "human_summary": payload["human_summary"],
                "action_label": payload["action_label"],
                "model_label": payload["model_label"],
                "document_label": payload["document_label"],
                "field_label_display": payload["field_label_display"],
                "before_display": payload["before_display"],
                "after_display": payload["after_display"],
                "search_text": payload["search_text"],
                "result": "Registrado"
                if vals.get("operation_type") != "event"
                else "Evento registrado",
            }
        )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [self._prepare_forensic_fields(vals) for vals in vals_list]
        return super().create(prepared)

    @api.model
    def action_open_document_history(self, model_name, record_id, record_name=None):
        title = record_name or f"{model_label(model_name)} #{record_id}"
        return {
            "type": "ir.actions.act_window",
            "name": f"Historia — {title}",
            "res_model": "justech.audit.log",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("justech_global_audit_log.view_justech_audit_log_timeline").id, "list"),
                (False, "form"),
            ],
            "domain": [("model_name", "=", model_name), ("record_id", "=", record_id)],
            "limit": 80,
        }

    def action_open_related_history(self):
        self.ensure_one()
        return self.action_open_document_history(
            self.model_name, self.record_id, self.record_name
        )

    def init(self):
        super().init()
        cr = self.env.cr
        tools.create_index(
            cr,
            "justech_audit_log_model_record_date_idx",
            self._table,
            ["model_name", "record_id", "change_date"],
        )
        tools.create_index(
            cr,
            "justech_audit_log_company_date_idx",
            self._table,
            ["company_id", "change_date"],
        )
        tools.create_index(
            cr,
            "justech_audit_log_user_date_idx",
            self._table,
            ["user_id", "change_date"],
        )
        tools.create_index(
            cr,
            "justech_audit_log_search_text_idx",
            self._table,
            ["search_text"],
        )

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        self._warn_wide_date_range(domain)
        return super().search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def _warn_wide_date_range(self, domain):
        date_from = None
        date_to = None
        for term in domain or []:
            if not isinstance(term, (list, tuple)) or len(term) != 3:
                continue
            field, operator, value = term
            if field != "change_date":
                continue
            if operator in (">=", ">"):
                date_from = value
            elif operator in ("<=", "<"):
                date_to = value
        if not date_from:
            return
        try:
            start = fields.Datetime.to_datetime(date_from)
            end = fields.Datetime.to_datetime(date_to) if date_to else fields.Datetime.now()
            if (end - start).days > 90:
                import logging

                logging.getLogger(__name__).info(
                    "Auditoría: consulta de más de 90 días (%s → %s)",
                    start,
                    end,
                )
        except (TypeError, ValueError):
            pass

    @api.model
    def _backfill_forensic_fields(self, batch_size=500):
        logs = self.search(
            ["|", ("human_summary", "=", False), ("human_summary", "=", "")],
            limit=batch_size,
            order="id desc",
        )
        for log in logs.with_context(justech_internal_log=True):
            payload = build_display_payload(
                {
                    "operation_type": log.operation_type,
                    "model_name": log.model_name,
                    "model_description": log.model_description,
                    "record_name": log.record_name,
                    "record_id": log.record_id,
                    "field_name": log.field_name,
                    "field_description": log.field_description,
                    "old_value": log.old_value,
                    "new_value": log.new_value,
                },
                user_name=log.user_id.name if log.user_id else "Sistema",
            )
            super(JustechAuditLog, log).write(
                {
                    "human_summary": payload["human_summary"],
                    "action_label": payload["action_label"],
                    "model_label": payload["model_label"],
                    "document_label": payload["document_label"],
                    "field_label_display": payload["field_label_display"],
                    "before_display": payload["before_display"],
                    "after_display": payload["after_display"],
                    "search_text": payload["search_text"],
                }
            )
        return len(logs)

    def write(self, vals):
        if self.env.context.get("justech_internal_log"):
            return super().write(vals)
        raise AccessError("Los registros de auditoría son inmutables.")

    def unlink(self):
        if self.env.context.get("justech_retention_purge"):
            return super().unlink()
        raise AccessError("Los registros de auditoría no pueden eliminarse manualmente.")

    @api.model
    def _purge_before(self, cutoff_date, batch_size=5000):
        total = 0
        while True:
            records = self.with_context(justech_retention_purge=True).search(
                [("change_date", "<", cutoff_date)],
                limit=batch_size,
                order="id",
            )
            if not records:
                break
            count = len(records)
            records.unlink()
            total += count
            if count < batch_size:
                break
        return total
