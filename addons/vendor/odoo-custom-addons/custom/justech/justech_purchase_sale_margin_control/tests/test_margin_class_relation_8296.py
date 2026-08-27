# -*- coding: utf-8 -*-
"""19.0.8.29.6 — Class UNION + relation status independent of Complete."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginClassRelation8296(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env["purchase.sale.cost.vs.sale.report"]
        cls.company = cls.env.company

    def _report(self, **vals):
        defaults = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "company_id": self.company.id,
            "company_ids": [(6, 0, self.company.ids)],
            "show_complete": True,
            "show_incomplete": False,
            "show_sales_without_cost": False,
            "show_costs_without_sale": False,
            "show_all_operations": False,
            "relation_filter": "all",
            "vendor_payment_state": "all",
            "customer_payment_state": "all",
            "vendor_doc_type": "all",
        }
        defaults.update(vals)
        return self.Report.create(defaults)

    def test_01_complete_plus_cost_is_union(self):
        r_c = self._report(show_complete=True, show_costs_without_sale=False)
        r_both = self._report(show_complete=True, show_costs_without_sale=True)
        allowed_c = set(r_c._allowed_relation_classes())
        allowed_b = set(r_both._allowed_relation_classes())
        self.assertTrue(allowed_c <= allowed_b)
        self.assertIn("incomplete_historical", allowed_b)
        # Complete classes still present after adding cost-without-sale
        for k in ("complete", "partial_with_cost"):
            self.assertIn(k, allowed_b)

    def test_02_payment_does_not_broaden_class(self):
        r_all = self._report(vendor_payment_state="all")
        r_pay = self._report(vendor_payment_state="not_paid")
        self.assertEqual(
            set(r_all._allowed_relation_classes()),
            set(r_pay._allowed_relation_classes()),
        )

    def test_03_todas_expands_union(self):
        r = self._report(show_all_operations=True, show_complete=False)
        flags = r._operation_type_flags()
        self.assertEqual(flags, (True, True, True, True))
        self.assertIn("incomplete_historical", r._allowed_relation_classes())
        self.assertIn("complete", r._allowed_relation_classes())

    def test_04_relation_status_helpers(self):
        Tx = self.env["purchase.sale.margin.transaction"]
        # empty → unrelated when no both
        st, badge = self.Report._relation_status_for(Tx, False, True)
        self.assertEqual(st, "unrelated")
        self.assertIn("RELACIONAR", badge.upper())

    def test_05_complete_blocks_not_cost_only(self):
        r = self._report(show_complete=True, relation_filter="all")
        for b in r._get_filtered_report_blocks():
            self.assertFalse(b.get("incomplete_cost_only"))

    def test_06_qweb_prepare_still_safe(self):
        r = self._report()
        grand = r._prepare_qweb_grand()
        self.assertIn("sales", grand)
        keys = set(grand.keys())
        _ = grand.get("sales") or grand.get("operations") or []
        self.assertEqual(set(grand.keys()), keys)

    def test_07_wizard_has_relation_filter_field(self):
        self.assertIn("relation_filter", self.Report._fields)
        self.assertIn("show_all_operations", self.Report._fields)
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_cost_vs_sale_report_form"
        )
        arch = view.arch_db or ""
        self.assertIn("relation_filter", arch)
        self.assertIn("show_all_operations", arch)

    def test_08_op_included_union_matrix(self):
        """A/B complete; C cost-only; D sale-only — checkbox UNION."""
        Tx = self.env["purchase.sale.margin.transaction"]
        tx = Tx.new({"state": "validated", "report_relation_class": "complete"})

        def op(has_sale, has_cost, klass="complete"):
            return {
                "sale": {
                    "untaxed": 100.0 if has_sale else 0.0,
                    "invoice_label": "INV" if has_sale else "",
                    "moves": False,
                    "is_superseded": False,
                },
                "costs": (
                    [{"include_in_margin": True, "untaxed": 40.0}] if has_cost else []
                ),
                "tx": tx,
            }

        # Complete only → A/B (both), not C/D
        r = self._report(show_complete=True)
        self.assertTrue(r._op_included(op(True, True)))
        self.assertFalse(r._op_included(op(False, True)))
        self.assertFalse(r._op_included(op(True, False)))

        # Complete + Cost without sale → A/B/C
        r2 = self._report(show_complete=True, show_costs_without_sale=True)
        self.assertTrue(r2._op_included(op(True, True)))
        self.assertTrue(r2._op_included(op(False, True)))
        self.assertFalse(r2._op_included(op(True, False)))

        # Cost without sale only → C
        r3 = self._report(show_complete=False, show_costs_without_sale=True)
        self.assertFalse(r3._op_included(op(True, True)))
        self.assertTrue(r3._op_included(op(False, True)))

        # Sale without cost → D
        r4 = self._report(
            show_complete=False,
            show_sales_without_cost=True,
        )
        self.assertTrue(r4._op_included(op(True, False)))
        self.assertFalse(r4._op_included(op(True, True)))

        # Todas → all classes
        r5 = self._report(show_all_operations=True, show_complete=False)
        self.assertTrue(r5._op_included(op(True, True)))
        self.assertTrue(r5._op_included(op(False, True)))
        self.assertTrue(r5._op_included(op(True, False)))

    def test_09_complete_allowed_excludes_cost_only_class(self):
        r = self._report(show_complete=True)
        self.assertNotIn("incomplete_historical", r._allowed_relation_classes())
        self.assertIn("complete", r._allowed_relation_classes())
