# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo.tests.common import TransactionCase


class JustechApprovalCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "justech_approval_purchase_enabled": True,
                "justech_approval_sale_enabled": True,
                "justech_approval_invoice_enabled": True,
            }
        )
        cls.group_approver = cls.env.ref("justech_approval_flow.group_approver")
        cls.group_self = cls.env.ref("justech_approval_flow.group_self_approve")
        cls.user_requester = cls.env["res.users"].create(
            {
                "name": "Requester UAT",
                "login": "req_%s" % uuid4().hex[:8],
                "email": "requester@example.com",
                "group_ids": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("purchase.group_purchase_user").id,
                        cls.env.ref("sales_team.group_sale_salesman").id,
                        cls.env.ref("account.group_account_invoice").id,
                    ])
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_approver = cls.env["res.users"].create(
            {
                "name": "Approver UAT",
                "login": "appr_%s" % uuid4().hex[:8],
                "email": "approver@example.com",
                "group_ids": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.group_approver.id,
                        cls.env.ref("purchase.group_purchase_manager").id,
                        cls.env.ref("sales_team.group_sale_manager").id,
                        cls.env.ref("account.group_account_invoice").id,
                    ])
                ],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.user_outsider = cls.env["res.users"].create(
            {
                "name": "Outsider UAT",
                "login": "out_%s" % uuid4().hex[:8],
                "email": "outsider@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.company.write({"justech_approval_user_ids": [(6, 0, cls.user_approver.ids)]})
        cls.env["justech.approval.user.rule"].sudo().search([]).unlink()
        cls.env["justech.approval.user.rule"].create(
            {
                "user_id": cls.user_approver.id,
                "active": True,
                "approve_sale": True,
                "approve_purchase": True,
                "approve_invoice": True,
            }
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "justech.approval.public.base.url", "https://erp.justech.do"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://erp.justech.do"
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner Approval %s" % uuid4().hex[:6],
                "email": "partner@example.com",
                "customer_rank": 1,
                "supplier_rank": 1,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Approval %s" % uuid4().hex[:6],
                "type": "service",
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 100.0,
                "standard_price": 40.0,
            }
        )

    def _po(self):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.display_name,
                            "product_qty": 2.0,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )

    def _so(self, user=None):
        user = user or self.user_requester
        return (
            self.env["sale.order"]
            .with_user(user)
            .create(
                {
                    "partner_id": self.partner.id,
                    "company_id": self.company.id,
                    "user_id": user.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 3.0,
                                "price_unit": 100.0,
                            },
                        )
                    ],
                }
            )
        )

    def _invoice(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 150.0,
                        },
                    )
                ],
            }
        )
        return move
