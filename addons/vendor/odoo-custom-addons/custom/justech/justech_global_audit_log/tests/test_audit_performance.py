import time

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_global_audit_log")
class TestJustechAuditPerformance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, justech_audit_skip_license=True))
        cls.service = cls.env["justech.audit.service"]
        cls.policy = cls.env["justech.audit.policy"].with_context(active_test=False).search(
            [], limit=1
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

    def test_partner_write_overhead_bounded(self):
        """Smoke benchmark: 50 writes with audit should stay under 5s in CI."""
        self.policy.write({"active": True})
        self.rule.write({"active": True})
        self.service._invalidate_runtime_cache()
        partner = self.env["res.partner"].with_context(justech_skip_audit=True).create(
            {"name": "Perf Partner"}
        )
        start = time.perf_counter()
        for idx in range(50):
            partner.write({"comment": f"note-{idx}"})
        self._flush_postcommit()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5.0, f"Audit write overhead too high: {elapsed:.2f}s")
