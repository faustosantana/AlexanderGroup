# -*- coding: utf-8 -*-

import re
from uuid import uuid4

from unittest import SkipTest

from odoo.tests import HttpCase, tagged

from odoo.addons.justech_approval_flow.controllers.approval_controller import (
    safe_approval_redirect_path,
)


def _csrf(html):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else ""


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestTokenHttpFlow(HttpCase):
    @classmethod
    def setUpClass(cls):
        try:
            super().setUpClass()
        except Exception as exc:  # noqa: BLE001
            raise SkipTest("HTTP test server unavailable (prefork/no httpd): %s" % exc) from exc

    def _prepare(self):
        company = self.env.company
        company.write(
            {
                "justech_approval_purchase_enabled": True,
                "justech_approval_sale_enabled": True,
                "justech_approval_invoice_enabled": True,
            }
        )
        group = self.env.ref("justech_approval_flow.group_approver")
        password = "approver-pass-%s" % uuid4().hex[:8]
        approver = self.env["res.users"].create(
            {
                "name": "HTTP Approver",
                "login": "http_appr_%s" % uuid4().hex[:8],
                "password": password,
                "email": "http.approver@example.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id, group.id])],
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
            }
        )
        self.env["justech.approval.user.rule"].sudo().search(
            [("user_id", "=", approver.id)]
        ).unlink()
        self.env["justech.approval.user.rule"].create(
            {
                "user_id": approver.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": True,
                "approve_invoice": True,
            }
        )
        partner = self.env["res.partner"].create(
            {"name": "HTTP Partner", "email": "http.partner@example.com"}
        )
        product = self.env["product.product"].create(
            {
                "name": "HTTP Product",
                "type": "service",
                "sale_ok": True,
                "list_price": 100,
            }
        )
        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 80})
                ],
            }
        )
        so.action_justech_request_approval()
        request = so.justech_approval_request_id.sudo()
        raw = request._generate_token()
        return so, request, raw, approver, password

    def test_anonymous_get_redirects_to_login(self):
        _so, request, raw, _appr, _pwd = self._prepare()
        approve_path = "/justech/approval/%s/approve" % raw
        page = self.url_open(approve_path, allow_redirects=False)
        # auth=user → SessionExpired → /web/login?redirect=...
        self.assertIn(page.status_code, (303, 302, 301))
        loc = page.headers.get("Location") or ""
        self.assertIn("/web/login", loc)
        self.assertIn("redirect=", loc)
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")

    def test_http_approve_authenticated(self):
        _so, request, raw, approver, password = self._prepare()
        approve_path = "/justech/approval/%s/approve" % raw
        self.authenticate(approver.login, password)
        page = self.url_open(approve_path)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("APROBAR SOLICITUD", html)
        csrf = _csrf(html)
        self.assertTrue(csrf)
        posted = self.url_open(approve_path, data={"csrf_token": csrf})
        self.assertEqual(posted.status_code, 200)
        self.assertIn("APROBACI", posted.content.decode().upper())
        request.invalidate_recordset()
        self.assertEqual(request.state, "approved")
        self.assertTrue(request.token_used)

    def test_http_reject_requires_reason(self):
        _so, request, raw, approver, password = self._prepare()
        reject_path = "/justech/approval/%s/reject" % raw
        self.authenticate(approver.login, password)
        page = self.url_open(reject_path)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("RECHAZAR SOLICITUD", html)
        csrf = _csrf(html)
        missing = self.url_open(reject_path, data={"csrf_token": csrf, "reason": ""})
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")
        self.assertTrue(missing.status_code in (200, 400))
        ok = self.url_open(
            reject_path, data={"csrf_token": csrf, "reason": "margen insuficiente"}
        )
        self.assertEqual(ok.status_code, 200)
        self.assertIn("RECHAZO", ok.content.decode().upper())
        request.invalidate_recordset()
        self.assertEqual(request.state, "rejected")

    def test_http_csrf_required_no_approve(self):
        _so, request, raw, approver, password = self._prepare()
        approve_path = "/justech/approval/%s/approve" % raw
        self.authenticate(approver.login, password)
        page = self.url_open(approve_path)
        self.assertEqual(page.status_code, 200)
        bad = self.url_open(approve_path, data={"csrf_token": "not-a-csrf"}, allow_redirects=False)
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")
        # Bad CSRF → login redirect (friendly) or 400; must NOT approve
        self.assertTrue(bad.status_code in (200, 302, 303, 400, 403))

    def test_get_cannot_approve(self):
        _so, request, raw, approver, password = self._prepare()
        approve_path = "/justech/approval/%s/approve" % raw
        self.authenticate(approver.login, password)
        page = self.url_open(approve_path)
        self.assertEqual(page.status_code, 200)
        self.assertIn("APROBAR", page.content.decode().upper())
        request.invalidate_recordset()
        self.assertEqual(request.state, "pending")

    def test_safe_redirect_helper(self):
        self.assertEqual(
            safe_approval_redirect_path("/justech/approval/abcTOKEN/approve"),
            "/justech/approval/abcTOKEN/approve",
        )
        self.assertFalse(safe_approval_redirect_path("https://evil.example/phish"))
        self.assertFalse(safe_approval_redirect_path("//evil.example/x"))
        self.assertFalse(safe_approval_redirect_path("/web"))
