# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..models.url_utils import (
    align_public_url_with_web_base,
    is_cross_environment,
    normalize_public_base_url,
)
from .common import JustechApprovalCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApprovalPublicUrl(JustechApprovalCase):
    def test_dev_urls_use_dev_host(self):
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = request._generate_token()
        approve = request.with_context(justech_approval_token=raw)._justech_url("approve")
        reject = request.with_context(justech_approval_token=raw)._justech_url("reject")
        view = request._odoo_document_url()
        for url in (approve, reject, view):
            self.assertTrue(url.startswith("https://erp.justech.do/"), url)
            self.assertNotIn("justgroup.app", url)
            self.assertNotIn("localhost", url)
            self.assertNotIn("127.0.0.1", url)

    def test_prod_like_urls_use_justgroup(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("web.base.url", "https://justgroup.app")
        icp.set_param("justech.approval.public.base.url", "https://justgroup.app")
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = request._generate_token()
        approve = request.with_context(justech_approval_token=raw)._justech_url("approve")
        self.assertTrue(approve.startswith("https://justgroup.app/"), approve)
        self.assertNotIn("erp.justech.do", approve)

    def test_cross_environment_url_is_realigned(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("web.base.url", "https://erp.justech.do")
        icp.set_param("justech.approval.public.base.url", "https://justgroup.app")
        self.assertTrue(
            is_cross_environment("https://justgroup.app", "https://erp.justech.do")
        )
        aligned = align_public_url_with_web_base(
            "https://justgroup.app", "https://erp.justech.do"
        )
        self.assertEqual(aligned, "https://erp.justech.do")
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = request._generate_token()
        approve = request.with_context(justech_approval_token=raw)._justech_url("approve")
        self.assertTrue(approve.startswith("https://erp.justech.do/"), approve)
        self.assertNotIn("justgroup.app", approve)

    def test_rejects_unsafe_scheme(self):
        with self.assertRaises(ValidationError):
            normalize_public_base_url("javascript:alert(1)")
        with self.assertRaises(ValidationError):
            normalize_public_base_url("http://justgroup.app")

    def test_normalizes_trailing_slash(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "justech.approval.public.base.url", "https://erp.justech.do/"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://erp.justech.do"
        )
        base = self.env["justech.approval.request"].get_public_base_url()
        self.assertEqual(base, "https://erp.justech.do")


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApproverRules(JustechApprovalCase):
    def test_sale_only_approver(self):
        sale_only = self.env["res.users"].create(
            {
                "name": "Sale Only",
                "login": "saleonly_%s" % self.user_approver.id,
                "email": "saleonly@example.com",
                "group_ids": [(6, 0, self.user_approver.group_ids.ids)],
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        self.env["justech.approval.user.rule"].create(
            {
                "user_id": sale_only.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": False,
                "approve_invoice": False,
            }
        )
        so = self._so()
        so.action_justech_request_approval()
        request = so.justech_approval_request_id
        self.assertIn(sale_only, request.approver_ids)
        self.assertNotIn(
            sale_only,
            self.env["justech.approval.user.rule"].approvers_for_type("purchase_order"),
        )

    def test_no_approver_for_type_raises(self):
        self.env["justech.approval.user.rule"].search([]).write({"approve_purchase": False})
        self.company.write({"justech_approval_user_ids": [(5, 0, 0)]})
        po = self._po()
        with self.assertRaises(UserError) as err:
            self.env["justech.approval.request"]._create_for_document(po, "purchase_order")
        self.assertIn("No hay aprobadores configurados", str(err.exception))

    def test_approver_cannot_edit_rules(self):
        with self.assertRaises(AccessError):
            self.env["justech.approval.user.rule"].with_user(self.user_approver).create(
                {
                    "user_id": self.user_outsider.id,
                    "approve_sale": True,
                }
            )

    def test_outsider_cannot_edit_rules(self):
        with self.assertRaises(AccessError):
            self.env["justech.approval.user.rule"].with_user(self.user_outsider).create(
                {
                    "user_id": self.user_outsider.id,
                    "approve_sale": True,
                }
            )
