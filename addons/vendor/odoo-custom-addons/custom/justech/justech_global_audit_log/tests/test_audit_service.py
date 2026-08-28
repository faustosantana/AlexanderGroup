from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_global_audit_log")
class TestJustechAuditService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, justech_audit_skip_license=True))
        cls.service = cls.env["justech.audit.service"]
        cls.policy = cls.env["justech.audit.policy"].with_context(active_test=False).search(
            [], limit=1
        )
        if not cls.policy:
            cls.policy = cls.env["justech.audit.policy"].create(
                {"name": "Test policy", "active": False}
            )
        from odoo.addons.justech_global_audit_log.hooks import (
            _ensure_default_policy,
            _ensure_default_rules,
        )

        _ensure_default_policy(cls.env)
        _ensure_default_rules(cls.env)
        cls.rule = cls.env["justech.audit.rule"].sudo().with_context(active_test=False).search(
            [("model_id.model", "=", "res.partner")], limit=1
        )
        if not cls.rule:
            raise AssertionError("Missing res.partner audit rule")

    def _flush_postcommit(self):
        self.env.cr.postcommit.run()

    def _enable_partner_audit(self):
        self.policy.write({"active": True})
        self.rule.write({"active": True})
        self.service._invalidate_runtime_cache()

    def _disable_partner_audit(self):
        self.policy.write({"active": False})
        self.rule.write({"active": False})
        self.service._invalidate_runtime_cache()

    def test_no_log_when_inactive(self):
        self._disable_partner_audit()
        before = self.env["justech.audit.log"].search_count(
            [("model_name", "=", "res.partner")]
        )
        self.env["res.partner"].create({"name": "Audit Inactive Partner"})
        self._flush_postcommit()
        after = self.env["justech.audit.log"].search_count(
            [("model_name", "=", "res.partner")]
        )
        self.assertEqual(before, after)

    def test_create_logs_when_active(self):
        self._enable_partner_audit()
        partner = self.env["res.partner"].create({"name": "Audit Active Partner"})
        self._flush_postcommit()
        logs = self.env["justech.audit.log"].search(
            [
                ("model_name", "=", "res.partner"),
                ("record_id", "=", partner.id),
                ("operation_type", "=", "create"),
            ]
        )
        self.assertEqual(len(logs), 1)
        self.assertIn("creó", logs.human_summary.lower())
        self.assertNotIn("__create__", logs.human_summary)
        self.assertEqual(logs.action_label, "Creó")
        self.assertNotIn("{", logs.after_display or "")

    def test_human_write_summary(self):
        self._enable_partner_audit()
        partner = self.env["res.partner"].with_context(justech_skip_audit=True).create(
            {"name": "Write Log Partner", "phone": "8090000000"}
        )
        partner.with_context(justech_skip_audit=True).write({"phone": "8090000001"})
        self.service.log_write(
            partner,
            {partner.id: {"phone": "8090000000"}},
            {"phone"},
        )
        logs = self.env["justech.audit.log"].search(
            [
                ("model_name", "=", "res.partner"),
                ("record_id", "=", partner.id),
                ("operation_type", "=", "write"),
                ("field_name", "=", "phone"),
            ]
        )
        self.assertTrue(logs)
        self.assertIn("8090000000", logs[0].old_value)
        self.assertIn("8090000001", logs[0].new_value)
        self.assertIn("cambió", logs[0].human_summary.lower())
        self.assertEqual(logs[0].action_label, "Modificó")
        self.assertEqual(logs[0].field_label_display, logs[0].field_description)

    def test_unlink_snapshot_display(self):
        self._enable_partner_audit()
        partner = self.env["res.partner"].with_context(justech_skip_audit=True).create(
            {"name": "Unlink Partner"}
        )
        snapshot = '{"name": "Unlink Partner"}'
        self.service.log_unlink(
            [
                {
                    "model_name": "res.partner",
                    "record_id": partner.id,
                    "record_name": partner.display_name,
                    "company_id": self.env.company.id,
                    "snapshot": snapshot,
                }
            ]
        )
        logs = self.env["justech.audit.log"].search(
            [
                ("model_name", "=", "res.partner"),
                ("record_id", "=", partner.id),
                ("operation_type", "=", "unlink"),
            ]
        )
        self.assertEqual(len(logs), 1)
        self.assertIn("eliminó", logs.human_summary.lower())
        self.assertEqual(logs.action_label, "Eliminó")
        self.assertNotIn("__unlink__", logs.field_label_display or "")

    def test_log_immutability(self):
        log = self.env["justech.audit.log"].sudo().create(
            {
                "operation_type": "event",
                "model_name": "res.partner",
                "model_description": "Contact",
                "record_id": 1,
                "record_name": "Test",
                "field_name": "__event__",
                "field_description": "Test",
                "old_value": "",
                "new_value": "{}",
            }
        )
        with self.assertRaises(Exception):
            log.write({"record_name": "Changed"})

    def test_governance_bridge_event(self):
        self.policy.write({"active": True, "audit_events": True})
        self.service._invalidate_runtime_cache()
        self.service.log_governance_event(
            "enable_feature",
            model="hellenia.feature.policy",
            res_id=99,
            details={"feature_code": "demo"},
            correlation_id="test-corr-1",
        )
        self._flush_postcommit()
        logs = self.env["justech.audit.log"].search(
            [
                ("operation_type", "=", "event"),
                ("correlation_id", "=", "test-corr-1"),
            ]
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs.event_source, "hellenia_governance")

    def test_excluded_user_skips_audit(self):
        self._enable_partner_audit()
        exclude = self.env["justech.audit.user.exclude"].create(
            {"user_id": self.env.user.id, "reason": "test"}
        )
        self.service._invalidate_runtime_cache()
        before = self.env["justech.audit.log"].search_count(
            [("model_name", "=", "res.partner")]
        )
        self.env["res.partner"].create({"name": "Excluded User Partner"})
        self._flush_postcommit()
        after = self.env["justech.audit.log"].search_count(
            [("model_name", "=", "res.partner")]
        )
        self.assertEqual(before, after)
        exclude.unlink()
        self.service._invalidate_runtime_cache()
