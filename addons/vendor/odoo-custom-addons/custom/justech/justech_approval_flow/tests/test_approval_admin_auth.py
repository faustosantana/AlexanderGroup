# -*- coding: utf-8 -*-
"""1.3.7 — Admin global + rule-based _can_decide (multi-company)."""
from uuid import uuid4

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApprovalAdminAuth(JustechApprovalCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env["justech.approval.request"]
        cls.company_b = cls.env["res.company"].create({"name": "Other Co Auth %s" % uuid4().hex[:6]})
        cls.user_system = cls.env["res.users"].create(
            {
                "name": "System Admin Auth",
                "login": "sys_auth_%s" % uuid4().hex[:8],
                "email": "sys.auth@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_system").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, (cls.company | cls.company_b).ids)],
            }
        )
        cls.user_mgr = cls.env["res.users"].create(
            {
                "name": "Approval Manager Auth",
                "login": "mgr_auth_%s" % uuid4().hex[:8],
                "email": "mgr.auth@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("justech_approval_flow.group_manager").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_rule_only = cls.env["res.users"].create(
            {
                "name": "Rule Only Auth",
                "login": "rule_auth_%s" % uuid4().hex[:8],
                "email": "rule.auth@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.env["justech.approval.user.rule"].sudo().search(
            [("user_id", "in", (cls.user_rule_only | cls.user_system).ids)]
        ).unlink()
        cls.env["justech.approval.user.rule"].create(
            {
                "user_id": cls.user_rule_only.id,
                "company_id": cls.company.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": False,
                "approve_invoice": False,
                "allow_self_approval": False,
            }
        )

    def _pending_sale_request(self):
        so = self._so()
        so.action_justech_request_approval()
        return so.justech_approval_request_id.sudo()

    def test_system_admin_sale_without_group_approver(self):
        """Fausto-like: Settings admin + company access, no group_approver."""
        req = self._pending_sale_request()
        self.assertFalse(self.user_system.has_group("justech_approval_flow.group_approver"))
        self.assertTrue(self.Request._is_approval_admin(self.user_system))
        req.with_user(self.user_system)._can_decide(token_flow=True)

    def test_system_admin_cross_company_deny(self):
        req = self._pending_sale_request()
        req.write({"company_id": self.company_b.id})
        with self.assertRaises(AccessError):
            req.with_user(self.user_system)._can_decide(token_flow=True)

    def test_approval_manager_without_rule_row(self):
        req = self._pending_sale_request()
        self.assertTrue(self.user_mgr.has_group("justech_approval_flow.group_manager"))
        req.with_user(self.user_mgr)._can_decide(token_flow=True)

    def test_rule_only_user_sale_allow(self):
        req = self._pending_sale_request()
        req.with_user(self.user_rule_only)._can_decide(token_flow=True)

    def test_rule_only_user_no_sale_flag_deny(self):
        req = self._pending_sale_request()
        req.with_user(self.user_outsider)
        with self.assertRaises(AccessError):
            req.with_user(self.user_outsider)._can_decide(token_flow=True)

    def test_self_approval_respects_company_rule(self):
        req = self._pending_sale_request()
        req.write({"requester_id": self.user_rule_only.id})
        with self.assertRaises(AccessError):
            req.with_user(self.user_rule_only)._can_decide(token_flow=True)
