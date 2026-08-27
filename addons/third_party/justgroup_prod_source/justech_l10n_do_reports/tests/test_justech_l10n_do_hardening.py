from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestJustechL10nDoReportsHardening(TransactionCase):
    def test_fiscal_report_record_rules(self):
        for model_name in (
            "justech.do.fiscal.report",
            "justech.do.fiscal.report.line",
            "justech.do.fiscal.report.wizard",
        ):
            rules = self.env["ir.rule"].search(
                [("model_id.model", "=", model_name)]
            )
            self.assertTrue(
                rules.filtered(lambda r: "company" in (r.domain_force or "")),
                f"Missing company rule for {model_name}",
            )
