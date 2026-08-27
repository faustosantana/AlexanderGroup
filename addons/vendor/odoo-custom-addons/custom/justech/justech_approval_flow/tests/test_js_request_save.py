# -*- coding: utf-8 -*-

import os

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestJsRequestSave(TransactionCase):
    def test_js_patch_uses_native_save_and_debounce(self):
        path = os.path.join(
            get_module_path("justech_approval_flow"),
            "static/src/js/form_request_approval_save.js",
        )
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("beforeExecuteActionButton", content)
        self.assertIn("super.beforeExecuteActionButton", content)
        self.assertIn("_justechApprovalBusy", content)
        self.assertIn("action_justech_request_approval", content)
        self.assertIn("action_justech_open_request_wizard", content)
        self.assertIn("No se puede solicitar aprobación porque faltan datos obligatorios", content)

    def test_js_asset_in_backend_bundle(self):
        manifest = get_manifest("justech_approval_flow") or {}
        backend = (manifest.get("assets") or {}).get("web.assets_backend") or []
        self.assertIn(
            "justech_approval_flow/static/src/js/form_request_approval_save.js",
            backend,
        )
        unit = (manifest.get("assets") or {}).get("web.assets_unit_tests") or []
        self.assertIn(
            "justech_approval_flow/static/tests/form_request_approval_save.test.js",
            unit,
        )
