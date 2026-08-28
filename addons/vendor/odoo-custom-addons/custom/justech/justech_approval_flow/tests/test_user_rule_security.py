# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestUserRuleSecurity(JustechApprovalCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["justech.approval.user.rule"]
        cls.rule = cls.Rule.search([("user_id", "=", cls.user_approver.id)], limit=1)
        cls.user_settings = cls.env["res.users"].create(
            {
                "name": "Settings Admin Rule",
                "login": "settings_rule_%s" % uuid4().hex[:8],
                "email": "settings.rule@example.com",
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
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_mgr = cls.env["res.users"].create(
            {
                "name": "Approval Manager Rule",
                "login": "mgr_rule_%s" % uuid4().hex[:8],
                "email": "mgr.rule@example.com",
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
        cls.user_sale = cls.env["res.users"].create(
            {
                "name": "Salesman Rule",
                "login": "sale_rule_%s" % uuid4().hex[:8],
                "email": "sale.rule@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_purchase = cls.env["res.users"].create(
            {
                "name": "Buyer Rule",
                "login": "po_rule_%s" % uuid4().hex[:8],
                "email": "po.rule@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("purchase.group_purchase_user").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_account = cls.env["res.users"].create(
            {
                "name": "Accounting Rule",
                "login": "acc_rule_%s" % uuid4().hex[:8],
                "email": "acc.rule@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("account.group_account_invoice").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.self_approver = cls.env["res.users"].create(
            {
                "name": "Self Approve Rule",
                "login": "self_rule_%s" % uuid4().hex[:8],
                "email": "self.rule@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("justech_approval_flow.group_self_approve").id,
                        ],
                    )
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )

    def _as(self, user):
        return self.Rule.with_user(user)

    def _assert_no_read(self, user):
        rule = self._as(user)
        with self.assertRaises(AccessError):
            rule.search([])
        with self.assertRaises(AccessError):
            rule.search_read([], ["user_id"])
        with self.assertRaises(AccessError):
            rule.browse(self.rule.id).read(["user_id", "email", "approve_sale"])
        with self.assertRaises(AccessError):
            rule.name_search("")
        try:
            count = rule.search_count([])
        except AccessError:
            count = None
        else:
            self.assertEqual(count, 0)
        if hasattr(rule, "web_search_read"):
            try:
                with self.assertRaises(AccessError):
                    rule.web_search_read(domain=[], specification={"id": {}})
            except (TypeError, ValueError):
                with self.assertRaises(AccessError):
                    rule.web_search_read([])
        with self.assertRaises(AccessError):
            rule.create({"user_id": user.id, "approve_sale": True})
        with self.assertRaises(AccessError):
            self.rule.with_user(user).write({"approve_sale": False})
        with self.assertRaises(AccessError):
            self.rule.with_user(user).unlink()
        try:
            rule.browse(self.rule.id).export_data(["user_id"])
        except (AccessError, UserError):
            pass
        else:
            self.fail("export_data should be denied")

    def test_acl_xmlid_removed(self):
        self.assertFalse(
            self.env.ref(
                "justech_approval_flow.access_justech_approval_user_rule_read",
                raise_if_not_found=False,
            )
        )

    def test_settings_admin_crud(self):
        rule = self._as(self.user_settings)
        self.assertTrue(rule.search([]))
        self.assertTrue(rule.search_read([], ["user_id"]))
        self.assertTrue(self.rule.with_user(self.user_settings).read(["user_id"]))
        extra = self.env["res.users"].create(
            {
                "name": "Tmp Rule User",
                "login": "tmp_rule_%s" % uuid4().hex[:8],
                "email": "tmp.rule@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        created = rule.create(
            {
                "user_id": extra.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": False,
                "approve_invoice": False,
            }
        )
        created.with_user(self.user_settings).write({"approve_invoice": True})
        created.with_user(self.user_settings).unlink()

    def test_approval_manager_crud(self):
        rule = self._as(self.user_mgr)
        self.assertTrue(rule.search_read([], ["user_id"]))
        extra = self.env["res.users"].create(
            {
                "name": "Tmp Mgr Rule User",
                "login": "tmp_mgr_rule_%s" % uuid4().hex[:8],
                "email": "tmp.mgr.rule@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        created = rule.create(
            {
                "user_id": extra.id,
                "approve_purchase": True,
            }
        )
        created.with_user(self.user_mgr).write({"active": False})
        created.with_user(self.user_mgr).unlink()

    def test_approver_cannot_read_rules(self):
        self._assert_no_read(self.user_approver)

    def test_self_approve_group_cannot_read_rules(self):
        self._assert_no_read(self.self_approver)

    def test_salesman_cannot_read_rules(self):
        self._assert_no_read(self.user_sale)

    def test_purchase_user_cannot_read_rules(self):
        self._assert_no_read(self.user_purchase)

    def test_accounting_user_cannot_read_rules(self):
        self._assert_no_read(self.user_account)

    def test_normal_user_cannot_read_rules(self):
        self._assert_no_read(self.user_outsider)

    def test_config_menu_hidden_from_approver(self):
        menu = self.env.ref("justech_approval_flow.menu_justech_approval_config")
        groups = menu.group_ids if "group_ids" in menu._fields else menu.groups_id
        self.assertIn(self.env.ref("justech_approval_flow.group_manager"), groups)
        self.assertIn(self.env.ref("base.group_system"), groups)
        self.assertFalse(self.user_approver.has_group("justech_approval_flow.group_manager"))
        self.assertFalse(self.user_approver.has_group("base.group_system"))
        self.assertTrue(self.user_settings.has_group("base.group_system"))

    def test_config_action_exists(self):
        action = self.env.ref("justech_approval_flow.action_justech_approval_user_rule")
        self.assertEqual(action.res_model, "justech.approval.user.rule")

    def test_routing_without_approver_config_read(self):
        with self.assertRaises(AccessError):
            self.Rule.with_user(self.user_approver).search([])
        so = self._so()
        so.action_justech_request_approval(note="routing without config read")
        request = so.justech_approval_request_id
        self.assertTrue(request)
        self.assertIn(self.user_approver, request.approver_ids)
        mail = self.env["mail.mail"].sudo().search(
            [("model", "=", "justech.approval.request"), ("res_id", "=", request.id)],
            limit=1,
        )
        self.assertTrue(mail)
        self.assertIn((self.user_approver.email or "").lower(), (mail.email_to or "").lower())
        acts = so.activity_ids
        self.assertTrue(acts)
        request.with_user(self.user_approver).action_approve(note="ok")
        self.assertEqual(request.state, "approved")
        result = self.env["mail.mail"].sudo().search(
            [
                ("model", "=", "justech.approval.request"),
                ("res_id", "=", request.id),
                ("subject", "ilike", "APROBADA"),
            ]
        )
        self.assertTrue(result)

    def test_purchase_and_invoice_route_without_config_read(self):
        po = self._po()
        po.with_context(justech_approval_wizard_submit=True).action_justech_request_approval()
        self.assertIn(self.user_approver, po.justech_approval_request_id.approver_ids)
        inv = self._invoice()
        inv.action_justech_request_approval()
        self.assertIn(self.user_approver, inv.justech_approval_request_id.approver_ids)
        action = inv.with_context(justech_approval_force_wizard=True).action_post()
        self.assertEqual(action.get("res_model"), "justech.approval.sale.confirm.wizard")
