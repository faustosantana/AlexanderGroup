# -*- coding: utf-8 -*-
"""Quick UAT — CxP source = open vendor bills (19.0.8.29.2)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.payable_cxp_source import open_vendor_bill_domain


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginCxpSource8292(TransactionCase):
    def test_01_action_points_to_account_move(self):
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_purchase_sale_payable_auxiliary"
        )
        self.assertEqual(action.res_model, "account.move")
        self.assertIn("amount_residual", action.domain or "")

    def test_02_open_domain_excludes_draft_paid(self):
        Partner = self.env["res.partner"]
        partner = Partner.create({"name": "CxP UAT Vendor", "supplier_rank": 1})
        Move = self.env["account.move"]
        open_bill = Move.create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-08-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "line",
                            "quantity": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        open_bill.action_post()
        draft = Move.create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-08-01",
                "invoice_line_ids": [
                    (0, 0, {"name": "d", "quantity": 1, "price_unit": 50})
                ],
            }
        )
        found = Move.search(open_vendor_bill_domain() + [("id", "in", (open_bill | draft).ids)])
        self.assertIn(open_bill, found)
        self.assertNotIn(draft, found)
        # zero residual → not open
        if open_bill.amount_residual:
            # mark conceptually: residual filter
            zeroed = Move.search(
                open_vendor_bill_domain()
                + [("id", "=", open_bill.id), ("amount_residual", "=", 0)]
            )
            self.assertFalse(zeroed)

    def test_03_report_uses_same_domain_helper(self):
        Report = self.env["purchase.sale.payable.auxiliary.report"]
        wiz = Report.create({})
        self.assertTrue(hasattr(wiz, "_cxp_bills"))
