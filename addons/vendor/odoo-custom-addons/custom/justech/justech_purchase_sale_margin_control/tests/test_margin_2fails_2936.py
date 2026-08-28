# -*- coding: utf-8 -*-
"""Regression: functional PO→SO link ACL + display_cost no double-count."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
    assert_po_link_authorized,
)


@tagged("post_install", "-at_install", "justech_margin")
class TestFunctionalPoLinkAndDisplayCost2936(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "UAT 2936 Customer"})
        cls.vendor = cls.env["res.partner"].create(
            {"name": "UAT 2936 Vendor", "supplier_rank": 1}
        )
        cls.po_product = cls.env["product.product"].create(
            {"name": "PAPEL TOALLA EN ROLLOS 6 UAT", "type": "consu", "list_price": 10.0}
        )
        cls.so_product = cls.env["product.product"].create(
            {"name": "PAPEL TOALLA UAT", "type": "consu", "list_price": 20.0}
        )
        cls.so = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.so_product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        cls.po = cls.env["purchase.order"].create(
            {
                "partner_id": cls.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.po_product.id,
                            "product_qty": 1,
                            "price_unit": 50.0,
                            "name": cls.po_product.display_name,
                        },
                    )
                ],
            }
        )
        # Purchase + margin purchase only — NO sales / accounting / admin.
        cls.func_user = cls.env["res.users"].create(
            {
                "name": "UAT Functional Link 2936",
                "login": "uat_functional_link_2936",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("purchase.group_purchase_user").id,
                            cls.env.ref(
                                "justech_purchase_sale_margin_control.group_margin_purchase"
                            ).id,
                        ],
                    )
                ],
            }
        )

    def test_functional_user_can_link_po_to_so(self):
        """Purchase+margin user completes Vincular a venta without Sales role."""
        self.assertFalse(
            self.func_user.has_group("sales_team.group_sale_salesman")
        )
        self.assertFalse(
            self.func_user.has_group("justech_purchase_sale_margin_control.group_margin_admin")
        )
        env_u = self.env(user=self.func_user)
        assert_po_link_authorized(
            env_u, self.po, self.so, self.partner, customer_invoice=None
        )
        wiz = env_u["purchase.sale.link.sale.wizard"].create(
            {
                "purchase_order_id": self.po.id,
                "company_id": self.po.company_id.id,
                "customer_id": self.partner.id,
                "sale_order_id": self.so.id,
            }
        )
        wiz._validate_client_step()
        wiz._rebuild_match_lines()
        self.assertTrue(wiz.line_ids)
        self.assertTrue(wiz.line_ids[:1].sale_line_id)
        self.assertEqual(
            wiz.line_ids[:1].sale_line_id.product_id, self.so_product
        )

    def test_confirmed_real_cost_does_not_double_estimated_cost(self):
        """When estimated == real (fallback), display_cost must equal real once."""
        tx = self.env["purchase.sale.margin.transaction"].create(
            {
                "name": "UAT-2936-DBL",
                "company_id": self.env.company.id,
                "sale_order_ids": [(6, 0, [self.so.id])],
                "customer_id": self.partner.id,
            }
        )
        # Simulate finance KPI fallback: estimated copied from real.
        tx.invalidate_recordset()
        # Write stored computes via SQL-less invalidate after setting via fields
        # Use sudo write on compute-stored? They are computed — set via context
        # by creating cost lines: one confirmed real 22100; estimated lines excluded.
        self.env["purchase.sale.margin.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "line_type": "cost",
                "cost_source": "direct_purchase",
                "data_origin": "accounting",
                "state": "confirmed",
                "quantity": 1.0,
                "amount_untaxed": 22100.0,
                "product_id": self.so_product.id,
                "sale_order_id": self.so.id,
                "description": "Vendor bill real",
            }
        )
        tx.invalidate_recordset()
        # Force estimated == real the way production does (fallback when est lines excluded)
        # by checking compute: if no estimated lines, est becomes real.
        est = tx.cost_estimated_amount
        real = tx.cost_real_amount
        self.assertTrue(float_compare(real, 22100.0, precision_digits=2) == 0)
        # Regardless of estimated fallback, display must not be 2x real
        self.assertEqual(
            float_compare(tx.display_cost_amount, real, precision_digits=2),
            0,
            "display=%s est=%s real=%s" % (tx.display_cost_amount, est, real),
        )
        self.assertNotEqual(
            float_compare(tx.display_cost_amount, real * 2, precision_digits=2),
            0,
        )
