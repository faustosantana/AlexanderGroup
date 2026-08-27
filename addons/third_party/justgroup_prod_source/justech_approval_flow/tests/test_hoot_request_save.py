# -*- coding: utf-8 -*-

from unittest import SkipTest

from odoo.tests import HttpCase, tagged


def _hoot_error_checker(message):
    return "[HOOT]" not in message


@tagged("post_install", "-at_install", "justech_approval_flow", "justech_approval_hoot")
class TestHootRequestSave(HttpCase):
    @classmethod
    def setUpClass(cls):
        try:
            super().setUpClass()
        except Exception as exc:  # noqa: BLE001
            raise SkipTest("HOOT browser unavailable on this host: %s" % exc) from exc

    def test_hoot_justech_approval_request_save(self):
        self.browser_js(
            "/web/tests?headless&loglevel=2&preset=desktop&timeout=20000&filter=justech_approval_flow.request_save",
            "",
            "",
            login="admin",
            timeout=180,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=_hoot_error_checker,
        )
