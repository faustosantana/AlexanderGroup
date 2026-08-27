# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_approval_flow")
class TestApprovalRegressionCompat(TransactionCase):
    def test_module_installed_and_views_load(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_approval_flow")], limit=1
        )
        self.assertEqual(mod.state, "installed")
        self.assertEqual(mod.latest_version, "19.0.1.3.5")
        self.env.ref("justech_approval_flow.view_justech_approval_request_list")
        self.env.ref("justech_approval_flow.action_justech_approval_pending")
        self.env.ref("justech_approval_flow.action_justech_approval_user_rule")
        self.env.ref("justech_approval_flow.mail_template_approval_request")
        self.env.ref("justech_approval_flow.mail_template_approval_result")

    def test_sale_confirm_when_disabled(self):
        company = self.env.company
        company.justech_approval_sale_enabled = False
        partner = self.env["res.partner"].create({"name": "Reg SO", "customer_rank": 1})
        product = self.env["product.product"].create(
            {"name": "Reg Prod", "type": "consu", "sale_ok": True, "list_price": 10}
        )
        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 10})],
            }
        )
        so.with_context(justech_approval_force_wizard=True).action_confirm()
        self.assertEqual(so.state, "sale")

    def test_trace_margin_vbc_still_present(self):
        trace = self.env["ir.module.module"].search(
            [("name", "=", "justech_sale_purchase_trace")], limit=1
        )
        if trace.state == "installed":
            self.assertTrue(
                hasattr(self.env["sale.order"], "action_justech_buy_pending")
                or "justech_qty_pending_purchase" in self.env["sale.order.line"]._fields
            )
        margin = self.env["ir.module.module"].search(
            [("name", "=", "justech_purchase_sale_margin_control")], limit=1
        )
        if margin.state == "installed":
            self.assertTrue(hasattr(self.env["purchase.order"], "_justech_auto_link_margin_from_sale"))
        vbc = self.env["ir.module.module"].search(
            [("name", "=", "justech_vendor_bill_po_control")], limit=1
        )
        if vbc.state == "installed":
            self.assertIn("vendor_bill_approval_state", self.env["account.move"]._fields)

    def test_purchase_native_states_unchanged(self):
        selection = dict(self.env["purchase.order"]._fields["state"].selection)
        self.assertIn("draft", selection)
        self.assertIn("sent", selection)
        self.assertIn("to approve", selection)
        self.assertIn("purchase", selection)

    def test_no_qweb_watermark_views(self):
        self.assertFalse(
            self.env.ref(
                "justech_approval_flow.report_purchaseorder_document_justech_banner",
                raise_if_not_found=False,
            )
        )
        self.assertFalse(
            self.env.ref(
                "justech_approval_flow.report_saleorder_document_justech_banner",
                raise_if_not_found=False,
            )
        )

    def test_purchase_user_can_read_po_with_cost_links(self):
        if "purchase.sale.cost.link" not in self.env:
            return
        self.env["justech.approval.request"]._ensure_cost_link_purchase_read()
        partner = self.env["res.partner"].create({"name": "ACL Vendor", "supplier_rank": 1})
        product = self.env["product.product"].create(
            {"name": "ACL Prod", "type": "service", "purchase_ok": True}
        )
        user = self.env["res.users"].create(
            {
                "name": "Buyer ACL",
                "login": "buyer_acl_%s" % partner.id,
                "email": "buyer.acl@example.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("purchase.group_purchase_user").id,
                        ],
                    )
                ],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, self.env.company.ids)],
            }
        )
        po = (
            self.env["purchase.order"]
            .with_user(user)
            .create(
                {
                    "partner_id": partner.id,
                    "order_line": [
                        (0, 0, {"product_id": product.id, "name": product.name, "product_qty": 1, "price_unit": 10})
                    ],
                }
            )
        )
        po.with_user(user).read(["name", "state", "partner_id"])
        if "cost_link_count" in po._fields:
            po.with_user(user).read(["cost_link_count"])
