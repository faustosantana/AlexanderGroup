import base64
import csv
import io

from odoo import fields, models


class JustechAuditExportWizard(models.TransientModel):
    _name = "justech.audit.export.wizard"
    _description = "Justech Audit Export Wizard"

    date_from = fields.Datetime()
    date_to = fields.Datetime()
    model_name = fields.Char(string="Modelo técnico")
    operation_type = fields.Selection(
        [
            ("create", "Creación"),
            ("write", "Modificación"),
            ("unlink", "Eliminación"),
            ("event", "Evento"),
        ]
    )
    company_id = fields.Many2one("res.company")
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    def action_export_csv(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(("change_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("change_date", "<=", self.date_to))
        if self.model_name:
            domain.append(("model_name", "=", self.model_name))
        if self.operation_type:
            domain.append(("operation_type", "=", self.operation_type))
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))

        logs = self.env["justech.audit.log"].sudo().search(domain, order="change_date desc, id desc")
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "change_date",
                "operation_type",
                "model_name",
                "model_description",
                "record_id",
                "record_name",
                "field_name",
                "field_description",
                "old_value",
                "new_value",
                "user_id",
                "company_id",
                "ip_address",
                "event_source",
                "correlation_id",
            ]
        )
        for log in logs:
            writer.writerow(
                [
                    fields.Datetime.to_string(log.change_date),
                    log.operation_type,
                    log.model_name,
                    log.model_description,
                    log.record_id,
                    log.record_name,
                    log.field_name,
                    log.field_description,
                    log.old_value,
                    log.new_value,
                    log.user_id.display_name,
                    log.company_id.display_name,
                    log.ip_address,
                    log.event_source,
                    log.correlation_id,
                ]
            )
        payload = base64.b64encode(buffer.getvalue().encode("utf-8"))
        filename = "justech_audit_export.csv"
        self.write({"file_data": payload, "file_name": filename})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
