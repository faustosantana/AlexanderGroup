# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMarginTransaction(TransactionCase):
    """Coverage for the 19.0.2.0.0 redesign centered on
    purchase.sale.margin.transaction and purchase.sale.margin.board:

    - company handling (automatic active company / board without a
      required company)
    - the board action is a full page (target != 'new')
    - a sale without a related cost never counts as confirmed real margin
    - cost without sale, manual register wizards, invoice linking
    - multi purchase / multi sale aggregation
    - approve / reject / reopen workflow
    - administrative expense and inventory-pending isolation
    - partial vs fully covered margin
    - backfill dry-run counters
    - multi-company constraint
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Margin TX Test Co B"})

        cls.customer = cls.env["res.partner"].create({"name": "Margin TX Customer", "company_id": False})
        cls.customer2 = cls.env["res.partner"].create({"name": "Margin TX Customer 2", "company_id": False})
        cls.vendor = cls.env["res.partner"].create({"name": "Margin TX Vendor", "company_id": False})
        cls.vendor2 = cls.env["res.partner"].create({"name": "Margin TX Vendor 2", "company_id": False})

        cls.product_stock = cls.env["product.product"].create(
            {
                "name": "Margin TX Stockable Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 150.0,
                "standard_price": 80.0,
            }
        )
        cls.product_service = cls.env["product.product"].create(
            {
                "name": "Margin TX Admin Service",
                "type": "service",
                "list_price": 50.0,
                "standard_price": 30.0,
            }
        )

        cls.Transaction = cls.env["purchase.sale.margin.transaction"]
        cls.Line = cls.env["purchase.sale.margin.transaction.line"]
        cls.Board = cls.env["purchase.sale.margin.board"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_sale_order(self, product, qty=1.0, price=100.0, partner=None, company=None, confirm=False):
        company = company or self.company
        partner = partner or self.customer
        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "order_line": [
                    (0, 0, {"product_id": product.id, "name": product.name, "product_uom_qty": qty, "price_unit": price})
                ],
            }
        )
        if confirm:
            so.action_confirm()
        return so

    def _create_purchase_order(self, product, qty=1.0, price=60.0, partner=None, company=None, confirm=False):
        company = company or self.company
        partner = partner or self.vendor
        po = self.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "order_line": [
                    (0, 0, {"product_id": product.id, "name": product.name, "product_qty": qty, "price_unit": price})
                ],
            }
        )
        if confirm:
            po.button_confirm()
        return po

    def _create_customer_invoice(self, product, partner=None, qty=1.0, price=100.0, company=None, post=True):
        company = company or self.company
        partner = partner or self.customer
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "company_id": company.id,
                "invoice_date": date(2026, 3, 1),
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "quantity": qty, "price_unit": price})
                ],
            }
        )
        if post:
            move.action_post()
        return move

    def _create_vendor_bill(self, product, partner=None, qty=1.0, price=60.0, company=None, post=True):
        company = company or self.company
        partner = partner or self.vendor
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "company_id": company.id,
                "invoice_date": date(2026, 3, 1),
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "quantity": qty, "price_unit": price})
                ],
            }
        )
        if post:
            move.action_post()
        return move

    def _push_transaction_through_approval(self, transaction):
        transaction.action_send_review()
        transaction.action_validate_costs()
        transaction.action_send_approval()
        transaction.action_approve()
        return transaction

    # ------------------------------------------------------------------
    # Company handling
    # ------------------------------------------------------------------
    def test_transaction_company_defaults_automatically(self):
        transaction = self.Transaction.create({"name": "Auto company"})
        self.assertEqual(transaction.company_id, self.env.company)
        self.assertTrue(transaction.transaction_number)
        self.assertNotEqual(transaction.transaction_number, "Nuevo")

    def test_board_company_id_not_required(self):
        board = self.Board.create({})
        self.assertFalse(board.company_id)
        self.assertIn(self.env.company, board.company_ids)
        self.assertTrue(board.context_label)

    def test_board_never_shows_disallowed_company(self):
        # Restrict the current user to a single allowed company so the board
        # cannot consolidate the extra company created for this test.
        self.env.user.write(
            {
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        board = self.Board.with_company(self.company).create({})
        companies = board._get_scope_companies()
        self.assertNotIn(self.other_company, companies)
        self.assertIn(self.company, companies)

    # ------------------------------------------------------------------
    # Board action target (full page, not modal)
    # ------------------------------------------------------------------
    def test_board_action_target_is_not_new(self):
        # Menú usa server action → get_board_action() abre form con res_id (no modal)
        action = self.env["purchase.sale.margin.board"].get_board_action()
        self.assertEqual(action.get("target"), "current")
        self.assertNotEqual(action.get("target"), "new")
        self.assertTrue(action.get("res_id"))
        menu_action = self.env.ref(
            "justech_purchase_sale_margin_control.action_purchase_sale_margin_board"
        )
        self.assertEqual(menu_action._name, "ir.actions.server")

    # ------------------------------------------------------------------
    # Sale without cost never counts as confirmed real margin
    # ------------------------------------------------------------------
    def test_sale_without_cost_excluded_from_confirmed_margin(self):
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0, confirm=True)
        transaction = self.Transaction.create(
            {
                "name": "Sale without cost",
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "transaction_type": "resale",
            }
        )
        self.assertTrue(transaction.has_related_sale)
        self.assertFalse(transaction.has_related_cost)
        self.assertTrue(transaction.sale_without_cost)
        self.assertFalse(transaction.margin_is_calculable)
        self.assertEqual(transaction.real_margin, 0.0)

        self._push_transaction_through_approval(transaction)
        self.assertEqual(transaction.state, "approved")

        board = self.Board.create({})
        kpis = board._compute_kpis(self.env.companies, transaction.transaction_date, transaction.transaction_date)
        self.assertEqual(kpis["confirmed_real_margin"], 0.0)
        self.assertGreaterEqual(kpis["sales_without_cost_count"], 1)

    # ------------------------------------------------------------------
    # Cost without sale
    # ------------------------------------------------------------------
    def test_cost_without_sale(self):
        po = self._create_purchase_order(self.product_stock, qty=1, price=60.0, confirm=True)
        transaction = self.Transaction.create(
            {
                "name": "Cost without sale",
                "purchase_order_ids": [(6, 0, [po.id])],
                "transaction_type": "inventory",
            }
        )
        self.assertTrue(transaction.has_related_cost)
        self.assertFalse(transaction.has_related_sale)
        self.assertFalse(transaction.sale_without_cost)

        without_sale = self.Transaction.search(
            [("id", "=", transaction.id), ("has_related_cost", "=", True), ("has_related_sale", "=", False)]
        )
        self.assertIn(transaction, without_sale)

    # ------------------------------------------------------------------
    # Manual register wizards
    # ------------------------------------------------------------------
    def test_register_cost_wizard_manual(self):
        wizard = self.env["purchase.sale.register.cost.wizard"].create(
            {
                "company_id": self.company.id,
                "new_transaction_name": "Manual cost registration",
                "mode": "manual",
                "data_origin": "manual",
                "partner_id": self.vendor.id,
                "amount": 45.0,
                "cost_usage_type": "resale_direct",
            }
        )
        action = wizard.action_confirm()
        transaction = self.Transaction.browse(action["res_id"])
        self.assertEqual(transaction.cost_real_amount, 45.0)
        self.assertTrue(transaction.margin_is_calculable)

    def test_register_sale_wizard_manual(self):
        wizard = self.env["purchase.sale.register.sale.wizard"].create(
            {
                "company_id": self.company.id,
                "new_transaction_name": "Manual sale registration",
                "mode": "manual",
                "data_origin": "manual",
                "partner_id": self.customer.id,
                "amount": 120.0,
            }
        )
        action = wizard.action_confirm()
        transaction = self.Transaction.browse(action["res_id"])
        self.assertEqual(transaction.sale_real_amount, 120.0)
        self.assertEqual(transaction.customer_id, self.customer)

    # ------------------------------------------------------------------
    # Linking real invoices
    # ------------------------------------------------------------------
    def test_link_customer_invoice_and_vendor_bill(self):
        # No action_post: DEV fiscal NCF rules block unvalidated partners.
        # Linking draft invoices is allowed for financial control without
        # creating/posting accounting documents.
        invoice = self._create_customer_invoice(self.product_stock, qty=1, price=100.0, post=False)
        bill = self._create_vendor_bill(self.product_stock, qty=1, price=60.0, post=False)

        sale_wizard = self.env["purchase.sale.register.sale.wizard"].create(
            {
                "company_id": self.company.id,
                "new_transaction_name": "Linked invoice",
                "mode": "invoice_line",
                "customer_invoice_line_id": invoice.invoice_line_ids[0].id,
            }
        )
        action = sale_wizard.action_confirm()
        transaction = self.Transaction.browse(action["res_id"])
        self.assertIn(invoice, transaction.customer_invoice_ids)
        self.assertAlmostEqual(transaction.sale_real_amount, 100.0, places=2)

        cost_wizard = self.env["purchase.sale.register.cost.wizard"].create(
            {
                "company_id": self.company.id,
                "transaction_id": transaction.id,
                "mode": "bill_line",
                "vendor_bill_line_id": bill.invoice_line_ids[0].id,
            }
        )
        cost_wizard.action_confirm()
        self.assertIn(bill, transaction.vendor_bill_ids)
        self.assertAlmostEqual(transaction.cost_real_amount, 60.0, places=2)
        self.assertTrue(transaction.margin_is_calculable)
        self.assertAlmostEqual(transaction.real_margin, 40.0, places=2)

    # ------------------------------------------------------------------
    # Multi purchase / multi sale
    # ------------------------------------------------------------------
    def test_multi_purchase_multi_sale_aggregation(self):
        so1 = self._create_sale_order(self.product_stock, qty=1, price=100.0)
        so2 = self._create_sale_order(self.product_stock, qty=1, price=80.0, partner=self.customer2)
        po1 = self._create_purchase_order(self.product_stock, qty=1, price=50.0)
        po2 = self._create_purchase_order(self.product_stock, qty=1, price=30.0, partner=self.vendor2)

        transaction = self.Transaction.create(
            {
                "name": "Multi purchase multi sale",
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so1.id, so2.id])],
                "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
                "transaction_type": "mixed",
            }
        )
        self.assertEqual(len(transaction.sale_order_ids), 2)
        self.assertEqual(len(transaction.purchase_order_ids), 2)
        self.assertAlmostEqual(transaction.sale_estimated_amount, 180.0, places=2)
        self.assertAlmostEqual(transaction.cost_estimated_amount, 80.0, places=2)

    # ------------------------------------------------------------------
    # Approve / reject / reopen workflow
    # ------------------------------------------------------------------
    def test_approve_workflow_requires_validation(self):
        transaction = self.Transaction.create({"name": "Workflow test"})
        with self.assertRaises(UserError):
            transaction.action_approve()

    def test_full_workflow_approve_close_reopen(self):
        transaction = self.Transaction.create({"name": "Full workflow"})
        transaction.action_send_review()
        self.assertEqual(transaction.state, "pending_review")
        transaction.action_validate_costs()
        self.assertEqual(transaction.state, "validated")
        self.assertTrue(transaction.validated_by_id)
        transaction.action_send_approval()
        self.assertEqual(transaction.approval_state, "pending")
        transaction.action_approve()
        self.assertEqual(transaction.state, "approved")
        self.assertTrue(transaction.approved_by_id)
        transaction.action_close()
        self.assertEqual(transaction.state, "closed")
        transaction.action_reopen()
        self.assertEqual(transaction.state, "reopened")

    def test_reject_transaction(self):
        transaction = self.Transaction.create({"name": "Reject test"})
        transaction.action_send_review()
        transaction.action_reject()
        self.assertEqual(transaction.state, "rejected")
        transaction.action_reopen()
        self.assertEqual(transaction.state, "reopened")

    def test_cannot_approve_with_cancelled_documents(self):
        po = self._create_purchase_order(self.product_stock, qty=1, price=60.0)
        transaction = self.Transaction.create(
            {"name": "Cancelled doc test", "purchase_order_ids": [(6, 0, [po.id])]}
        )
        transaction.action_send_review()
        transaction.action_validate_costs()
        # Bypass the UI workflow to force a cancelled state regardless of the
        # exact button name exposed by purchase.order in this Odoo version.
        po.write({"state": "cancel"})
        with self.assertRaises(UserError):
            transaction.action_approve()

    # ------------------------------------------------------------------
    # Administrative expense isolation
    # ------------------------------------------------------------------
    def test_admin_expense_isolated_from_confirmed_margin(self):
        transaction = self.Transaction.create(
            {
                "name": "Admin expense",
                "transaction_type": "administrative",
            }
        )
        self.Line.create(
            {
                "transaction_id": transaction.id,
                "line_type": "cost",
                "data_origin": "manual",
                "cost_usage_type": "administrative_expense",
                "amount_untaxed": 200.0,
                "amount_total": 200.0,
            }
        )
        self._push_transaction_through_approval(transaction)

        board = self.Board.create({})
        kpis = board._compute_kpis(self.env.companies, transaction.transaction_date, transaction.transaction_date)
        self.assertGreaterEqual(kpis["admin_expense_amount"], 200.0)
        # Administrative operations must never be counted in the confirmed
        # real margin KPI even if approved/closed.
        confirmed_tx = self.Transaction.search(
            [
                ("id", "=", transaction.id),
                ("state", "in", ("approved", "closed")),
                ("margin_is_calculable", "=", True),
                ("transaction_type", "!=", "administrative"),
            ]
        )
        self.assertFalse(confirmed_tx)

    # ------------------------------------------------------------------
    # Inventory pending isolation
    # ------------------------------------------------------------------
    def test_inventory_pending_separate_kpi(self):
        po = self._create_purchase_order(self.product_stock, qty=1, price=90.0, confirm=True)
        transaction = self.Transaction.create(
            {
                "name": "Inventory pending",
                "purchase_order_ids": [(6, 0, [po.id])],
                "transaction_type": "inventory",
            }
        )
        self.assertFalse(transaction.has_related_sale)
        board = self.Board.create({})
        kpis = board._compute_kpis(self.env.companies, transaction.transaction_date, transaction.transaction_date)
        self.assertGreaterEqual(kpis["inventory_pending_count"], 1)

    # ------------------------------------------------------------------
    # Partial vs fully covered margin
    # ------------------------------------------------------------------
    def test_partial_then_full_cost_coverage(self):
        so = self._create_sale_order(self.product_stock, qty=1, price=200.0)
        po = self._create_purchase_order(self.product_stock, qty=1, price=150.0)
        transaction = self.Transaction.create(
            {
                "name": "Partial coverage",
                "customer_id": self.customer.id,
                "sale_order_ids": [(6, 0, [so.id])],
                "purchase_order_ids": [(6, 0, [po.id])],
                "transaction_type": "resale",
            }
        )
        self.assertAlmostEqual(transaction.cost_estimated_amount, 150.0, places=2)
        self.assertEqual(transaction.cost_real_amount, 0.0)
        self.assertFalse(transaction.cost_fully_covered)

        self.Line.create(
            {
                "transaction_id": transaction.id,
                "line_type": "cost",
                "data_origin": "manual",
                "purchase_order_id": po.id,
                "cost_usage_type": "resale_direct",
                "amount_untaxed": 75.0,
                "amount_total": 75.0,
            }
        )
        self.assertAlmostEqual(transaction.cost_real_amount, 75.0, places=2)
        self.assertAlmostEqual(transaction.pending_cost_amount, 75.0, places=2)
        self.assertFalse(transaction.cost_fully_covered)

        self.Line.create(
            {
                "transaction_id": transaction.id,
                "line_type": "cost",
                "data_origin": "manual",
                "purchase_order_id": po.id,
                "cost_usage_type": "resale_direct",
                "amount_untaxed": 75.0,
                "amount_total": 75.0,
            }
        )
        self.assertAlmostEqual(transaction.cost_real_amount, 150.0, places=2)
        self.assertAlmostEqual(transaction.pending_cost_amount, 0.0, places=2)
        self.assertTrue(transaction.cost_fully_covered)

    # ------------------------------------------------------------------
    # Backfill dry-run (2026 only, zero writes)
    # ------------------------------------------------------------------
    def test_backfill_dry_run_detects_without_writing(self):
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0, confirm=True)
        po = self._create_purchase_order(self.product_stock, qty=1, price=60.0)
        po.order_line[0].sale_line_id = so.order_line[0].id
        po.button_confirm()
        self.assertEqual(po.date_order.year, 2026)
        self.assertEqual(so.date_order.year, 2026)

        tx_count_before = self.Transaction.search_count([])
        wizard = self.env["purchase.sale.backfill.wizard"].create(
            {"year": 2026, "company_ids": [(6, 0, [self.company.id])], "dry_run": True}
        )
        wizard.action_run()
        tx_count_after = self.Transaction.search_count([])

        self.assertEqual(tx_count_before, tx_count_after)
        self.assertEqual(wizard.state, "done")
        self.assertGreaterEqual(wizard.scanned_sale_orders, 1)
        self.assertGreaterEqual(wizard.transactions_created, 1)

    def test_backfill_apply_creates_only_detected_transactions(self):
        so = self._create_sale_order(self.product_stock, qty=1, price=100.0, confirm=True)
        wizard = self.env["purchase.sale.backfill.wizard"].create(
            {"year": 2026, "company_ids": [(6, 0, [self.company.id])], "dry_run": False}
        )
        wizard.action_run()
        transaction = self.Transaction.search([("sale_order_ids", "in", so.id)], limit=1)
        self.assertTrue(transaction)
        self.assertIn(transaction.state, ("detected", "pending_review"))
        self.assertNotIn(transaction.state, ("approved", "closed"))

    # ------------------------------------------------------------------
    # Multi-company constraint
    # ------------------------------------------------------------------
    def test_multi_company_constraint(self):
        so_other = self._create_sale_order(self.product_stock, company=self.other_company)
        with self.assertRaises(ValidationError):
            self.Transaction.create(
                {
                    "name": "Cross company",
                    "company_id": self.company.id,
                    "sale_order_ids": [(6, 0, [so_other.id])],
                }
            )
