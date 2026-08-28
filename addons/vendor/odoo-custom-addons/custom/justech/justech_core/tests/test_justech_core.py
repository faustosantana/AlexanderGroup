# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)
from odoo.tests import TransactionCase


class TestModule(TransactionCase):
    """Placeholder — replace when models are implemented."""

    def test_module_installable(self):
        module = self.env["ir.module.module"].search([("name", "=", "justech_core")])
        self.assertTrue(module)
