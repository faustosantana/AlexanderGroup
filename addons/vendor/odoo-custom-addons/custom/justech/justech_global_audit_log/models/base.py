import json

from odoo import api, models, tools


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _justech_excluded_fields(self):
        return self.env["justech.audit.service"].get_excluded_fields(self._name)

    @api.model
    def _justech_should_audit(self, operation):
        if self.env.context.get("justech_skip_audit"):
            return False
        service = self.env["justech.audit.service"]
        if not service._runtime_enabled():
            return False
        return service.should_audit(
            self._name,
            operation,
            company_id=self.env.company.id,
            user_id=self.env.uid,
        )

    def _justech_capture_unlink_data(self):
        service = self.env["justech.audit.service"]
        data = []
        excluded = service.get_excluded_fields(self._name)
        for record in self:
            rec_sudo = record.sudo()
            snapshot = {}
            for field_name, field in record._fields.items():
                if field_name in excluded or field.type in service.SKIP_FIELD_TYPES:
                    continue
                snapshot[field_name] = service._format_value(
                    record._name, field_name, rec_sudo[field_name], record=rec_sudo
                )
            data.append(
                {
                    "model_name": record._name,
                    "record_id": record.id,
                    "record_name": rec_sudo.display_name,
                    "company_id": service._get_record_company_id(rec_sudo),
                    "snapshot": json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                }
            )
        return data

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records._justech_should_audit("create"):
            self.env["justech.audit.service"].log_create(records)
        return records

    def write(self, vals):
        if self.env.context.get("justech_skip_audit") or not self._justech_should_audit("write"):
            return super().write(vals)

        excluded = self._justech_excluded_fields()
        fields_to_check = {
            key
            for key in vals
            if key not in excluded
            and self._fields.get(key)
            and self._fields[key].type not in self.env["justech.audit.service"].SKIP_FIELD_TYPES
        }
        if not fields_to_check:
            return super().write(vals)

        # Capture previous values via sudo so field ACLs do not block writers.
        previous_values = {
            record.id: {field: record.sudo()[field] for field in fields_to_check}
            for record in self
        }
        result = super().write(vals)
        self.env["justech.audit.service"].log_write(self, previous_values, fields_to_check)
        return result

    def unlink(self):
        if self.env.context.get("justech_skip_audit") or not self._justech_should_audit("unlink"):
            return super().unlink()

        records_data = self._justech_capture_unlink_data()
        result = super().unlink()
        self.env["justech.audit.service"].log_unlink(records_data)
        return result
