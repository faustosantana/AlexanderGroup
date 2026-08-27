"""Integrity: every value produced by UI status computes must exist in Selection."""
import ast
import inspect

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_invoice_status")
class TestUiStatusSelectionIntegrity(TransactionCase):
    """Fails if compute emits a status absent from the Selection definition."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env["account.move"]

    def _selection_keys(self, field_name):
        field = self.Move._fields[field_name]
        return {k for k, _label in field._description_selection(self.env)}

    def _literal_assigns_from_compute(self, target_name):
        """Collect string literals assigned to ``target_name`` in the compute method."""
        src = inspect.getsource(self.Move._compute_justech_do_ui_statuses)
        src = inspect.cleandoc(src)
        tree = ast.parse(src)
        values = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == target_name:
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, str
                    ):
                        values.add(node.value.value)
        return values

    def test_computed_fiscal_literals_subset_of_selection(self):
        keys = self._selection_keys("justech_do_fiscal_ui_status")
        computed = self._literal_assigns_from_compute("fiscal")
        self.assertTrue(computed, "No fiscal literals found in compute method")
        orphan = computed - keys
        self.assertFalse(
            orphan,
            "Computed fiscal statuses missing from Selection: %s" % sorted(orphan),
        )

    def test_computed_operational_literals_subset_of_selection(self):
        keys = self._selection_keys("justech_do_operational_ui_status")
        computed = self._literal_assigns_from_compute("operational")
        orphan = computed - keys
        self.assertFalse(
            orphan,
            "Computed operational statuses missing from Selection: %s"
            % sorted(orphan),
        )

    def test_computed_payment_ui_literals_subset_of_selection(self):
        keys = self._selection_keys("justech_do_payment_ui_status")
        computed = self._literal_assigns_from_compute("payment_ui")
        # payment_ui may also mirror payment_state dynamically; ensure "other" exists
        self.assertIn("other", keys)
        orphan = computed - keys
        self.assertFalse(
            orphan,
            "Computed payment UI statuses missing from Selection: %s"
            % sorted(orphan),
        )

    def test_credit_note_issued_in_selection_and_live_refund(self):
        keys = self._selection_keys("justech_do_fiscal_ui_status")
        self.assertIn("credit_note_issued", keys)
        refund = self.Move.search(
            [
                ("move_type", "in", ("out_refund", "in_refund")),
                ("state", "=", "posted"),
                ("justech_do_ncf", "!=", False),
                ("justech_do_ncf_voided", "=", False),
            ],
            limit=1,
        )
        if not refund:
            self.skipTest("No posted credit note with NCF in this database")
        fiscal = refund.justech_do_fiscal_ui_status
        self.assertIn(fiscal, keys)
        # Traditional B04 → credit_note_issued; E34 → ecf_e34
        ncf = (refund.justech_do_ncf or "").upper()
        if ncf.startswith("E34"):
            self.assertEqual(fiscal, "ecf_e34")
        else:
            self.assertEqual(fiscal, "credit_note_issued")
        self.assertIn(
            refund.justech_do_payment_ui_status,
            self._selection_keys("justech_do_payment_ui_status"),
        )
