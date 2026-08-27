import json
import logging

from odoo import _, api, fields, models, tools
from odoo.http import request
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class JustechAuditService(models.AbstractModel):
    _name = "justech.audit.service"
    _description = "Justech Audit Service"

    TECHNICAL_MODELS = frozenset(
        {
            "justech.audit.log",
            "justech.audit.rule",
            "justech.audit.policy",
            "justech.audit.field.exclude",
            "justech.audit.user.exclude",
            "justech.audit.retention",
            "justech.audit.dashboard",
            "bus.bus",
            "bus.presence",
            "mail.message",
            "mail.followers",
            "mail.notification",
            "ir.logging",
            "ir.cron",
            "ir.model.data",
            "ir.attachment",
            "ir.sequence",
            "ir.ui.view",
            "ir.actions.act_window",
            "ir.config_parameter",
        }
    )

    SENSITIVE_FIELD_NAMES = frozenset(
        {
            "password",
            "password_crypt",
            "new_password",
            "confirm_password",
            "api_key",
            "access_token",
            "refresh_token",
            "signing_key",
            "private_key",
            "secret",
            "client_secret",
            "auth_code",
            "totp_secret",
        }
    )

    SKIP_FIELD_TYPES = frozenset({"one2many", "many2many", "binary", "html", "image"})

    NOISE_FIELDS = frozenset(
        {
            "write_date",
            "write_uid",
            "create_date",
            "create_uid",
            "message_ids",
            "activity_ids",
            "message_follower_ids",
            "message_partner_ids",
            "message_main_attachment_id",
            "website_message_ids",
            "access_token",
            "display_name",
        }
    )

    @api.model
    @tools.ormcache()
    def _runtime_enabled(self):
        """Fast path: any active policy + active rule."""
        return bool(
            self.env["justech.audit.policy"].sudo().search_count([("active", "=", True)], limit=1)
            and self.env["justech.audit.rule"].sudo().search_count([("active", "=", True)], limit=1)
        )

    @api.model
    def _invalidate_runtime_cache(self):
        self.env.registry.clear_cache()

    @api.model
    def _is_feature_licensed(self, company=None):
        if self.env.context.get("justech_audit_skip_license"):
            return True
        if "justech.license.service" not in self.env:
            return True
        company = company or self.env.company
        try:
            license_svc = self.env["justech.license.service"]
            if not license_svc.get_feature("global_audit"):
                return True
            return license_svc.is_active("global_audit", company=company)
        except Exception:
            _logger.debug("Justech license check skipped for global_audit", exc_info=True)
            return True

    @api.model
    @tools.ormcache()
    def _excluded_user_ids(self):
        return frozenset(
            self.env["justech.audit.user.exclude"]
            .sudo()
            .search([("active", "=", True)])
            .mapped("user_id")
            .ids
        )

    @api.model
    @tools.ormcache("model_name")
    def _global_excluded_field_names(self, model_name):
        FieldExclude = self.env["justech.audit.field.exclude"].sudo()
        global_names = set(
            FieldExclude.search([("model_id", "=", False)]).mapped("field_name")
        )
        model_names = set(
            FieldExclude.search([("model_id.model", "=", model_name)]).mapped("field_name")
        )
        return frozenset(global_names | model_names | self.SENSITIVE_FIELD_NAMES | self.NOISE_FIELDS)

    @api.model
    @tools.ormcache("model_name")
    def _get_rule_snapshot(self, model_name):
        rule = (
            self.env["justech.audit.rule"]
            .sudo()
            .search([("model_name", "=", model_name), ("active", "=", True)], limit=1)
        )
        if not rule:
            return None
        return {
            "id": rule.id,
            "audit_create": rule.audit_create,
            "audit_write": rule.audit_write,
            "audit_unlink": rule.audit_unlink,
            "company_ids": frozenset(rule.company_ids.ids),
            "field_exclude_names": frozenset(rule.field_exclude_ids.mapped("field_name")),
        }

    @api.model
    @tools.ormcache("company_id")
    def _get_policy_snapshot(self, company_id):
        Policy = self.env["justech.audit.policy"].sudo()
        policy = Policy.search(
            [("company_id", "=", company_id), ("active", "=", True)], limit=1
        )
        if not policy:
            policy = Policy.search(
                [("company_id", "=", False), ("active", "=", True)], limit=1
            )
        if not policy:
            return None
        return {
            "audit_create": policy.audit_create,
            "audit_write": policy.audit_write,
            "audit_unlink": policy.audit_unlink,
            "audit_events": policy.audit_events,
            "excluded_user_ids": frozenset(policy.excluded_user_ids.ids),
        }

    @api.model
    @tools.ormcache()
    def _policy_runtime_enabled(self):
        return bool(
            self.env["justech.audit.policy"].sudo().search_count([("active", "=", True)], limit=1)
        )

    @api.model
    def should_log_event(self, company_id=None, user_id=None):
        if not self._policy_runtime_enabled():
            return False
        user_id = user_id or self.env.uid
        if user_id in self._excluded_user_ids():
            return False
        company_id = company_id or self.env.company.id
        company = self.env["res.company"].browse(company_id)
        if not self._is_feature_licensed(company=company):
            return False
        policy = self._get_policy_snapshot(company_id)
        if not policy:
            return False
        if user_id in policy["excluded_user_ids"]:
            return False
        return bool(policy.get("audit_events"))

    @api.model
    def should_audit(self, model_name, operation, company_id=None, user_id=None):
        if model_name in self.TECHNICAL_MODELS:
            return False
        if not self._runtime_enabled():
            return False
        user_id = user_id or self.env.uid
        if user_id in self._excluded_user_ids():
            return False
        company_id = company_id or self.env.company.id
        company = self.env["res.company"].browse(company_id)
        if not self._is_feature_licensed(company=company):
            return False
        policy = self._get_policy_snapshot(company_id)
        if not policy:
            return False
        if user_id in policy["excluded_user_ids"]:
            return False
        op_field = {
            "create": "audit_create",
            "write": "audit_write",
            "unlink": "audit_unlink",
        }.get(operation)
        if not op_field or not policy.get(op_field):
            return False
        rule = self._get_rule_snapshot(model_name)
        if not rule:
            return False
        if not rule.get(op_field):
            return False
        if rule["company_ids"] and company_id not in rule["company_ids"]:
            return False
        return True

    @api.model
    def get_excluded_fields(self, model_name):
        rule = self._get_rule_snapshot(model_name) or {}
        return (
            self._global_excluded_field_names(model_name)
            | rule.get("field_exclude_names", frozenset())
        )

    @api.model
    def _get_request_meta(self):
        try:
            if request and request.httprequest:
                httprequest = request.httprequest
                user_agent = httprequest.user_agent.string if httprequest.user_agent else False
                return httprequest.remote_addr, user_agent
        except RuntimeError:
            pass
        return False, False

    @api.model
    def _get_ip_address(self):
        ip_address, _user_agent = self._get_request_meta()
        return ip_address

    @api.model
    def _get_model_description(self, model_name):
        model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        return model.name or model_name

    @api.model
    def _get_field_description(self, model_name, field_name):
        if field_name in ("__create__", "__unlink__", "__event__"):
            return field_name
        field = self.env[model_name]._fields.get(field_name)
        return field.string if field else field_name

    @api.model
    def _format_value(self, model_name, field_name, value, record=None):
        if value is False or value is None:
            return ""
        if field_name in self.SENSITIVE_FIELD_NAMES:
            return "[REDACTED]"
        if field_name in ("__create__", "__unlink__", "__event__"):
            return str(value)
        if model_name not in self.env:
            return str(value)
        field = self.env[model_name]._fields.get(field_name)
        if not field:
            return str(value)
        if field.type == "many2one":
            return value.display_name if value else ""
        if field.type in ("many2many", "one2many"):
            names = value.mapped("display_name")
            if len(names) > 20:
                preview = ", ".join(names[:20])
                return f"{preview} … (+{len(names) - 20} more)"
            return ", ".join(names)
        if field.type == "selection":
            selection = field.selection
            if callable(selection):
                selection = selection(record) if record else []
            selection = dict(selection or [])
            return selection.get(value, value)
        if field.type in ("monetary", "float"):
            return f"{value:.2f}"
        text = str(value)
        if len(text) > 2000:
            return f"{text[:2000]}…"
        return text

    @api.model
    def _get_record_company_id(self, record):
        if "company_id" in record._fields and record.company_id:
            return record.company_id.id
        return self.env.company.id

    @api.model
    def _build_entry(
        self,
        record,
        operation_type,
        field_name,
        old_value,
        new_value,
        *,
        event_source=None,
        correlation_id=None,
    ):
        model_name = record._name if record else False
        return {
            "operation_type": operation_type,
            "model_name": model_name,
            "model_description": self._get_model_description(model_name) if model_name else "",
            "record_id": record.id if record else 0,
            "record_name": record.display_name if record else "",
            "field_name": field_name,
            "field_description": self._get_field_description(model_name, field_name)
            if model_name
            else field_name,
            "old_value": old_value,
            "new_value": new_value,
            "user_id": self.env.uid,
            "company_id": self._get_record_company_id(record) if record else self.env.company.id,
            "change_date": fields.Datetime.now(),
            "ip_address": self._get_ip_address(),
            "user_agent": self._get_request_meta()[1],
            "event_source": event_source,
            "correlation_id": correlation_id,
        }

    @api.model
    def _write_entries_sync(self, entries):
        self.env["justech.audit.log"].sudo().with_context(
            justech_skip_audit=True,
            justech_internal_log=True,
        ).create(entries)

    @api.model
    def schedule_entries(self, entries):
        if not entries:
            return
        if tools.config["test_enable"] or self.env.context.get("justech_audit_sync"):
            self._write_entries_sync(entries)
            return
        cr = self.env.cr
        bucket = getattr(cr, "_justech_audit_pending_entries", None)
        if bucket is None:
            bucket = []
            cr._justech_audit_pending_entries = bucket
            dbname = cr.dbname
            uid = self.env.uid
            context = dict(self.env.context or {})

            def _flush_pending():
                if not bucket:
                    return
                try:
                    registry = Registry(dbname)
                    with registry.cursor() as new_cr:
                        env = api.Environment(new_cr, uid, context)
                        env["justech.audit.log"].sudo().with_context(
                            justech_skip_audit=True,
                            justech_internal_log=True,
                        ).create(list(bucket))
                        new_cr.commit()
                except Exception:
                    _logger.exception("Failed to flush Justech audit entries")
                finally:
                    bucket.clear()

            cr.postcommit.add(_flush_pending)
        bucket.extend(entries)

    @api.model
    def log_create(self, records):
        entries = []
        for record in records:
            excluded = self.get_excluded_fields(record._name)
            # Snapshot via sudo: field ACLs must not block operational users
            # when the audit engine captures values (e.g. signup_type).
            rec_sudo = record.sudo()
            snapshot = {}
            for field_name, field in record._fields.items():
                if field_name in excluded or field.type in self.SKIP_FIELD_TYPES:
                    continue
                if not field.store and not field.related:
                    continue
                snapshot[field_name] = self._format_value(
                    record._name, field_name, rec_sudo[field_name], record=rec_sudo
                )
            entries.append(
                self._build_entry(
                    record,
                    "create",
                    "__create__",
                    "",
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                )
            )
        self.schedule_entries(entries)

    @api.model
    def log_write(self, records, previous_values, changed_fields):
        entries = []
        for record in records:
            excluded = self.get_excluded_fields(record._name)
            rec_sudo = record.sudo()
            for field_name in changed_fields:
                if field_name in excluded:
                    continue
                field = record._fields.get(field_name)
                if field and field.type in self.SKIP_FIELD_TYPES:
                    continue
                old_text = self._format_value(
                    record._name,
                    field_name,
                    previous_values[record.id][field_name],
                    record=rec_sudo,
                )
                new_text = self._format_value(
                    record._name, field_name, rec_sudo[field_name], record=rec_sudo
                )
                if old_text == new_text:
                    continue
                entries.append(
                    self._build_entry(
                        record,
                        "write",
                        field_name,
                        old_text,
                        new_text,
                    )
                )
        self.schedule_entries(entries)

    @api.model
    def log_unlink(self, records_data):
        entries = []
        for data in records_data:
            entries.append(
                {
                    "operation_type": "unlink",
                    "model_name": data["model_name"],
                    "model_description": self._get_model_description(data["model_name"]),
                    "record_id": data["record_id"],
                    "record_name": data["record_name"],
                    "field_name": "__unlink__",
                    "field_description": "Eliminación",
                    "old_value": data["snapshot"],
                    "new_value": "",
                    "user_id": self.env.uid,
                    "company_id": data["company_id"],
                    "change_date": fields.Datetime.now(),
                    "ip_address": self._get_ip_address(),
                    "user_agent": self._get_request_meta()[1],
                }
            )
        self.schedule_entries(entries)

    @api.model
    def log_event(
        self,
        action,
        model=None,
        res_id=None,
        company=None,
        details=None,
        source="bridge",
        correlation_id=None,
    ):
        """Semantic event log — bridge for hellenia_governance and integrations."""
        company = company or self.env.company
        if not self.should_log_event(company_id=company.id):
            return False
        payload = {
            "action": action,
            "details": details or {},
            "source": source,
        }
        entry = {
            "operation_type": "event",
            "model_name": model or "justech.audit.event",
            "model_description": self._get_model_description(model)
            if model and model in self.env
            else (model or "Event"),
            "record_id": res_id or 0,
            "record_name": action,
            "field_name": "__event__",
            "field_description": action,
            "old_value": "",
            "new_value": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            "user_id": self.env.uid,
            "company_id": company.id,
            "change_date": fields.Datetime.now(),
            "ip_address": self._get_ip_address(),
            "user_agent": self._get_request_meta()[1],
            "event_source": source,
            "correlation_id": correlation_id,
        }
        self.schedule_entries([entry])
        return True

    @api.model
    def log_governance_event(
        self, action, model=None, res_id=None, company=None, details=None, correlation_id=None
    ):
        """Future bridge entrypoint for hellenia.governance.service.audit_event()."""
        return self.log_event(
            action,
            model=model,
            res_id=res_id,
            company=company,
            details=details,
            source="hellenia_governance",
            correlation_id=correlation_id,
        )
