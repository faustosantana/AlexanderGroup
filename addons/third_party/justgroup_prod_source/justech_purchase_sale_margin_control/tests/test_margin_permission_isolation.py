# -*- coding: utf-8 -*-
"""19.0.8.25.0 — Margin ACL isolation from standard Accounting/Sales/Purchase flows."""
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

from odoo.addons.justech_purchase_sale_margin_control.models import margin_acl

MARGIN_GROUPS = (
    "justech_purchase_sale_margin_control.group_margin_readonly",
    "justech_purchase_sale_margin_control.group_margin_auditor",
    "justech_purchase_sale_margin_control.group_margin_sales",
    "justech_purchase_sale_margin_control.group_margin_purchase",
    "justech_purchase_sale_margin_control.group_margin_finance",
    "justech_purchase_sale_margin_control.group_margin_admin",
)
RECOVERY_GROUP = "justech_accounting_recovery.group_accounting_recovery"


@tagged("post_install", "-at_install", "justech_margin", "justech_margin_acl")
class TestMarginPermissionIsolation(TransactionCase):
    """Standard Odoo flows must not raise AccessError on Margin models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "ACL Iso Customer 825", "company_id": False}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "ACL Iso Vendor 825", "company_id": False}
        )
        # Avoid NCF "pending_new" block when fiscal is enabled on DEV/PROD clones.
        if "justech_do_fiscal_config_state" in cls.customer._fields:
            cls.customer.justech_do_fiscal_config_state = "not_applicable"
            cls.vendor.justech_do_fiscal_config_state = "not_applicable"
        cls.product = cls.env["product.product"].create(
            {
                "name": "ACL Iso Product 825",
                "type": "consu",
                "list_price": 200.0,
                "standard_price": 80.0,
            }
        )

        cls.invoice_user = new_test_user(
            cls.env,
            login="uat_margin_acl_invoice_825",
            groups="account.group_account_invoice,base.group_user",
        )
        cls._strip_margin_groups(cls.invoice_user)

        cls.sales_user = new_test_user(
            cls.env,
            login="uat_margin_acl_sales_825",
            groups="sales_team.group_sale_salesman,base.group_user",
        )
        cls._strip_margin_groups(cls.sales_user)

        cls.purchase_user = new_test_user(
            cls.env,
            login="uat_margin_acl_purchase_825",
            groups="purchase.group_purchase_user,base.group_user",
        )
        cls._strip_margin_groups(cls.purchase_user)

        cls.margin_finance = new_test_user(
            cls.env,
            login="uat_margin_acl_finance_825",
            groups=(
                "justech_purchase_sale_margin_control.group_margin_finance,"
                "account.group_account_invoice,base.group_user"
            ),
        )
        cls.margin_admin = new_test_user(
            cls.env,
            login="uat_margin_acl_admin_825",
            groups=(
                "justech_purchase_sale_margin_control.group_margin_admin,"
                "account.group_account_manager,base.group_user"
            ),
        )

    @classmethod
    def _strip_margin_groups(cls, user):
        for xmlid in MARGIN_GROUPS:
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group and group in user.group_ids:
                user.write({"group_ids": [(3, group.id)]})

    def _assert_no_margin_groups(self, user):
        has_any = any(user.has_group(xmlid) for xmlid in MARGIN_GROUPS)
        self.assertFalse(has_any, "User unexpectedly has Margin groups: %s" % user.login)

    def _create_customer_invoice(self, env=None):
        env = env or self.env
        return env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 6, 15),
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

    def _create_vendor_bill(self, env=None):
        env = env or self.env
        return env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 6, 15),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 70.0,
                        },
                    )
                ],
            }
        )

    def _create_sale_order(self, env=None):
        env = env or self.env
        return env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 150.0,
                        },
                    )
                ],
            }
        )

    def _create_purchase_order(self, env=None, origin=False):
        env = env or self.env
        vals = {
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_qty": 1.0,
                        "price_unit": 70.0,
                    },
                )
            ],
        }
        if origin:
            vals["origin"] = origin
        return env["purchase.order"].create(vals)

    def _try_post_as(self, move, user):
        """Post as user; skip if fiscal/NCF setup blocks (not Margin ACL)."""
        try:
            move.with_user(user).action_post()
            return "posted"
        except UserError as exc:
            msg = str(exc).lower()
            if any(
                token in msg
                for token in (
                    "ncf",
                    "comprobante",
                    "rnc",
                    "fiscal",
                    "pendiente de validar",
                    "b01",
                    "rango",
                    "orden de compra",
                    "aprobación",
                    "enviar a aprobación",
                )
            ):
                # Still prove Margin post-hooks do not AccessError.
                move.with_user(user)._justech_auto_link_margin_documents()
                if move.move_type in ("in_invoice", "in_refund"):
                    move.with_user(user)._ensure_payable_auxiliary()
                return "hooks_ok_fiscal_blocked"
            raise

    # ------------------------------------------------------------------
    def test_invoice_open_user_without_margin(self):
        self._assert_no_margin_groups(self.invoice_user)
        move = self._create_customer_invoice()
        user_move = move.with_user(self.invoice_user)
        _ = user_move.margin_transaction_count
        _ = user_move.jm_related_purchase_order_count
        _ = user_move.margin_control_cost
        _ = user_move.read(["name", "state", "amount_untaxed", "margin_transaction_count"])
        self.assertEqual(user_move.state, "draft")

    def test_invoice_post_user_without_margin(self):
        self._assert_no_margin_groups(self.invoice_user)
        move = self._create_customer_invoice()
        result = self._try_post_as(move, self.invoice_user)
        self.assertIn(result, ("posted", "hooks_ok_fiscal_blocked"))
        if result == "posted":
            self.assertEqual(move.state, "posted")

    def test_customer_invoice_post_no_margin_acl_leak(self):
        self._assert_no_margin_groups(self.invoice_user)
        so = self._create_sale_order()
        so.action_confirm()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 6, 16),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 150.0,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )
        result = self._try_post_as(move, self.invoice_user)
        self.assertIn(result, ("posted", "hooks_ok_fiscal_blocked"))
        with self.assertRaises(AccessError):
            self.env["purchase.sale.margin.transaction"].with_user(
                self.invoice_user
            ).search([])

    def test_vendor_bill_post_no_margin_acl_leak(self):
        self._assert_no_margin_groups(self.invoice_user)
        bill = self._create_vendor_bill()
        result = self._try_post_as(bill, self.invoice_user)
        self.assertIn(result, ("posted", "hooks_ok_fiscal_blocked"))
        _ = bill.with_user(self.invoice_user).margin_transaction_count
        _ = bill.with_user(self.invoice_user).has_payable_auxiliary

    def test_sale_confirm_no_margin_acl_leak(self):
        self._assert_no_margin_groups(self.sales_user)
        # Create as the sales user to satisfy multi-company / salesperson rules.
        so = self._create_sale_order(env=self.env(user=self.sales_user))
        try:
            so.action_confirm()
        except AccessError as exc:
            # Must not be Margin MTX ACL.
            self.assertNotIn("purchase.sale.margin.transaction", str(exc))
            self.skipTest("SO confirm blocked by non-Margin record rules: %s" % exc)
        self.assertIn(so.state, ("sale", "done"))
        _ = so.margin_transaction_count
        _ = so.jm_related_purchase_order_count
        _ = so.estimated_margin

    def test_purchase_confirm_no_margin_acl_leak(self):
        self._assert_no_margin_groups(self.purchase_user)
        so = self._create_sale_order()
        so.action_confirm()
        po = self._create_purchase_order(
            env=self.env(user=self.purchase_user), origin=so.name
        )
        po.button_confirm()
        # 'to approve' is a valid purchase workflow state — not Margin ACL.
        self.assertIn(po.state, ("purchase", "done", "to approve"))
        _ = po.margin_transaction_count
        _ = po.jm_related_sale_order_count

    def test_internal_margin_autolink_does_not_block_post(self):
        self._assert_no_margin_groups(self.invoice_user)
        so = self._create_sale_order()
        so.action_confirm()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "invoice_date": date(2026, 6, 17),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 180.0,
                            "sale_line_ids": [(6, 0, so.order_line.ids)],
                        },
                    )
                ],
            }
        )
        result = self._try_post_as(move, self.invoice_user)
        self.assertIn(result, ("posted", "hooks_ok_fiscal_blocked"))
        with self.assertRaises(AccessError):
            self.env["purchase.sale.margin.transaction"].with_user(
                self.invoice_user
            ).search([])

    def test_margin_dashboard_denied_without_group(self):
        self._assert_no_margin_groups(self.invoice_user)
        Board = self.env["purchase.sale.margin.board"]
        with self.assertRaises(AccessError):
            Board.with_user(self.invoice_user).create(
                {
                    "company_id": self.company.id,
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                }
            )

    def test_margin_transaction_denied_without_group(self):
        self._assert_no_margin_groups(self.invoice_user)
        with self.assertRaises(AccessError):
            self.env["purchase.sale.margin.transaction"].with_user(
                self.invoice_user
            ).search([])
        with self.assertRaises(AccessError):
            self.env["purchase.sale.margin.transaction"].with_user(
                self.invoice_user
            ).create(
                {
                    "company_id": self.company.id,
                    "name": "SHOULD-FAIL",
                    "transaction_type": "resale",
                }
            )

    def test_margin_finance_access(self):
        Board = self.env["purchase.sale.margin.board"].with_user(self.margin_finance)
        board = Board.create(
            {
                "company_id": self.company.id,
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
            }
        )
        self.assertTrue(board.id)
        txs = self.env["purchase.sale.margin.transaction"].with_user(
            self.margin_finance
        ).search([], limit=5)
        if txs:
            txs.read(["name"])

    def test_margin_admin_access(self):
        txs = self.env["purchase.sale.margin.transaction"].with_user(self.margin_admin)
        rec = txs.create(
            {
                "company_id": self.company.id,
                "name": "ACL-ADMIN-OK",
                "transaction_type": "resale",
                "customer_id": self.customer.id,
            }
        )
        self.assertTrue(rec.id)
        board = self.env["purchase.sale.margin.board"].with_user(self.margin_admin).create(
            {
                "company_id": self.company.id,
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
            }
        )
        self.assertTrue(board.id)

    def test_vbc_gate_not_bypassed(self):
        import inspect

        from odoo.addons.justech_purchase_sale_margin_control.models import (
            account_move,
            margin_auto_link,
        )

        src = inspect.getsource(margin_auto_link.AccountMoveAutoLink.action_post)
        self.assertNotIn("self.sudo()", src)
        self.assertNotIn(".sudo().action_post", src)
        src2 = inspect.getsource(account_move.AccountMove.action_post)
        self.assertNotIn("self.sudo()", src2)
        src3 = inspect.getsource(
            margin_auto_link.AccountMoveAutoLink._justech_auto_link_margin_documents
        )
        self.assertIn("margin_acl.margin_transaction", src3)
        self.assertNotIn("self.sudo()", src3)

    def test_accounting_recovery_guard_not_bypassed(self):
        Mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "justech_accounting_recovery"), ("state", "=", "installed")],
            limit=1,
        )
        if not Mod:
            self.skipTest("justech_accounting_recovery not installed")
        move = self._create_customer_invoice()
        recovery = self.env.ref(RECOVERY_GROUP, raise_if_not_found=False)
        if not recovery:
            self.skipTest("recovery group missing")
        with self.assertRaises(AccessError):
            move.with_user(self.invoice_user).unlink()
        with self.assertRaises(AccessError):
            move.with_user(self.invoice_user).sudo().unlink()
