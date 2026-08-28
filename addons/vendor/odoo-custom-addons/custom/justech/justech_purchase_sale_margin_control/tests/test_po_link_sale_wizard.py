# -*- coding: utf-8 -*-
"""UAT: PO Vincular a venta — filtro cliente, ACL, idempotencia."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
    execute_po_to_sale_link,
)


@tagged("post_install", "-at_install", "justech_margin")
class TestPoLinkSaleWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LinkWizard = cls.env["purchase.sale.link.sale.wizard"]
        cls.partner_a = cls.env["res.partner"].create({"name": "UAT Cliente A PO Link"})
        cls.partner_b = cls.env["res.partner"].create({"name": "UAT Cliente B PO Link"})
        cls.product_a = cls.env["product.product"].create(
            {"name": "UAT Product A Link", "type": "consu", "list_price": 100.0}
        )
        cls.product_b = cls.env["product.product"].create(
            {"name": "UAT Product B Link", "type": "consu", "list_price": 50.0}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "UAT Vendor PO Link", "supplier_rank": 1}
        )
        cls.so_a1 = cls._create_sale(cls, cls.partner_a, cls.product_a, 10)
        cls.so_a2 = cls._create_sale(cls, cls.partner_a, cls.product_b, 5)
        cls.so_b1 = cls._create_sale(cls, cls.partner_b, cls.product_a, 3)

    @staticmethod
    def _create_sale(_cls, partner, product, qty):
        return _cls.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

    def _create_po(self, product, qty, partner=None):
        partner = partner or self.vendor
        return self.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_qty": qty,
                            "price_unit": 10.0,
                            "name": product.display_name,
                        },
                    )
                ],
            }
        )

    def _wiz(self, po, customer=None, sale=None):
        vals = {"purchase_order_id": po.id, "company_id": po.company_id.id}
        if customer:
            vals["customer_id"] = customer.id
        if sale:
            vals["sale_order_id"] = sale.id
        return self.LinkWizard.create(vals)

    def test_sale_domain_filters_by_customer(self):
        po = self._create_po(self.product_a, 2)
        wiz = self._wiz(po, customer=self.partner_a)
        allowed = self.env["sale.order"].search(wiz._sale_domain_list())
        self.assertIn(self.so_a1, allowed)
        self.assertIn(self.so_a2, allowed)
        self.assertNotIn(self.so_b1, allowed)

    def test_onchange_customer_clears_incompatible_sale(self):
        po = self._create_po(self.product_a, 2)
        wiz = self._wiz(po, customer=self.partner_a, sale=self.so_a1)
        wiz.customer_id = self.partner_b
        wiz._onchange_customer_id()
        self.assertFalse(wiz.sale_order_id)

    def test_server_validation_wrong_customer(self):
        po = self._create_po(self.product_a, 2)
        wiz = self._wiz(po, customer=self.partner_a, sale=self.so_b1)
        with self.assertRaises(ValidationError):
            wiz._validate_client_step()

    def test_link_confirm_creates_assignment(self):
        if "justech.purchase.sale.qty.assignment" not in self.env:
            self.skipTest("qty.assignment module not installed")
        po = self._create_po(self.product_a, 4)
        so = self._create_sale(self.partner_a, self.product_a, 4)
        pol = po.order_line.filtered(lambda l: l.product_id == self.product_a)
        sol = so.order_line[0]
        execute_po_to_sale_link(
            self.env,
            purchase_order=po,
            sale_order=so,
            customer=self.partner_a,
            allocation_rows=[
                {
                    "sale_line": sol,
                    "purchase_line": pol,
                    "quantity": 4.0,
                }
            ],
        )
        self.assertEqual(pol.sale_line_id.order_id, so)
        asg = self.env["justech.purchase.sale.qty.assignment"].search(
            [
                ("purchase_line_id", "=", pol.id),
                ("sale_line_id", "=", pol.sale_line_id.id),
                ("state", "=", "active"),
            ],
            limit=1,
        )
        self.assertTrue(asg)
        self.assertAlmostEqual(asg.quantity, 4.0)

    def test_wizard_opens_without_invoice_acl(self):
        po = self._create_po(self.product_a, 1)
        purchase_user = self.env["res.users"].create(
            {
                "name": "UAT Purchase No Accounting",
                "login": "uat_purchase_no_acct_%s" % po.id,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("purchase.group_purchase_user").id,
                            self.env.ref(
                                "justech_purchase_sale_margin_control.group_margin_purchase"
                            ).id,
                        ],
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(purchase_user).check_access("read")
        wiz = self.LinkWizard.with_user(purchase_user).create(
            {
                "purchase_order_id": po.id,
                "company_id": po.company_id.id,
                "customer_id": self.partner_a.id,
                "sale_order_id": self.so_a1.id,
            }
        )
        self.assertFalse(wiz.show_customer_invoice)
        wiz._validate_client_step()
        wiz._rebuild_match_lines()

    def test_sale_line_domain_includes_different_product(self):
        """CJO-0000735 case: PO product ≠ SO product — dropdown must not be empty."""
        po_product = self.env["product.product"].create(
            {"name": "PAPEL TOALLA EN ROLLOS 6", "type": "consu", "list_price": 10.0}
        )
        so_product = self.env["product.product"].create(
            {"name": "PAPEL TOALLA", "type": "consu", "list_price": 20.0}
        )
        so = self._create_sale(self.partner_a, so_product, 1)
        po = self._create_po(po_product, 1)
        wiz = self._wiz(po, customer=self.partner_a, sale=so)
        wiz._rebuild_match_lines()
        line = wiz.line_ids[:1]
        self.assertTrue(line)
        domain = eval(line.sale_line_domain)
        sols = self.env["sale.order.line"].search(domain)
        self.assertEqual(len(sols), 1)
        self.assertEqual(sols.product_id, so_product)
        self.assertEqual(line.sale_line_id, sols)
        self.assertAlmostEqual(line.qty_to_assign, 1.0)

    def test_single_so_line_suggested_when_products_differ(self):
        po_product = self.env["product.product"].create(
            {"name": "OC Variant", "type": "consu"}
        )
        so_product = self.env["product.product"].create(
            {"name": "SO Base", "type": "consu"}
        )
        so = self._create_sale(self.partner_a, so_product, 2)
        po = self._create_po(po_product, 2)
        wiz = self._wiz(po, customer=self.partner_a, sale=so)
        sale_line, qty = wiz._suggest_sale_line(
            po.order_line[:1],
            wiz._eligible_sale_lines(so),
            self.env["account.move"],
        )
        self.assertEqual(sale_line, so.order_line[:1])
        self.assertAlmostEqual(qty, 2.0)

    def test_cross_product_link_allowed_via_po_wizard_path(self):
        if "justech.purchase.sale.qty.assignment" not in self.env:
            self.skipTest("qty.assignment module not installed")
        po_product = self.env["product.product"].create(
            {"name": "PO Variant Roll", "type": "consu", "list_price": 10.0}
        )
        so_product = self.env["product.product"].create(
            {"name": "SO Base Towel", "type": "consu", "list_price": 20.0}
        )
        so = self._create_sale(self.partner_a, so_product, 1)
        po = self._create_po(po_product, 1)
        pol = po.order_line[:1]
        sol = so.order_line[:1]
        execute_po_to_sale_link(
            self.env,
            purchase_order=po,
            sale_order=so,
            customer=self.partner_a,
            allocation_rows=[
                {"sale_line": sol, "purchase_line": pol, "quantity": 1.0},
            ],
        )
        self.assertEqual(pol.sale_line_id, sol)
