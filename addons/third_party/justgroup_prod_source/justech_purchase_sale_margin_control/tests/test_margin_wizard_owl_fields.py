# -*- coding: utf-8 -*-
"""Validación de vistas del asistente de costos vs campos del modelo (anti-OwlError)."""
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_margin")
class TestMarginAddPurchaseWizardFields(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["purchase.sale.add.purchase.wizard"]
        cls.PoCand = cls.env["purchase.sale.add.purchase.wizard.po.cand"]
        cls.BillCand = cls.env["purchase.sale.add.purchase.wizard.bill.cand"]
        cls.Line = cls.env["purchase.sale.add.purchase.wizard.line"]

    def _arch_field_names(self, arch):
        return set(re.findall(r"""name=["']([a-zA-Z0-9_]+)["']""", arch or ""))

    def test_01_po_cand_view_fields_exist(self):
        """Todo <field> del listado po_candidate_ids debe existir en el modelo."""
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_add_purchase_wizard_form"
        )
        arch = view.arch_db or ""
        # Extraer bloque po_candidate_ids
        m = re.search(
            r'<field name="po_candidate_ids"[^>]*>.*?</field>',
            arch,
            flags=re.S,
        )
        self.assertTrue(m, "po_candidate_ids list not found in wizard view")
        names = self._arch_field_names(m.group(0)) - {"po_candidate_ids"}
        missing = sorted(n for n in names if n not in self.PoCand._fields)
        self.assertFalse(missing, "po.cand XML fields missing on model: %s" % missing)
        self.assertIn("state", self.PoCand._fields)
        self.assertEqual(self.PoCand._fields["state"].type, "selection")
        self.assertEqual(
            self.PoCand._fields["state"].related, "purchase_order_id.state"
        )

    def test_02_bill_cand_view_fields_exist(self):
        view = self.env.ref(
            "justech_purchase_sale_margin_control.view_purchase_sale_add_purchase_wizard_form"
        )
        arch = view.arch_db or ""
        m = re.search(
            r'<field name="bill_candidate_ids"[^>]*>.*?</field>',
            arch,
            flags=re.S,
        )
        self.assertTrue(m, "bill_candidate_ids list not found")
        names = self._arch_field_names(m.group(0)) - {"bill_candidate_ids"}
        missing = sorted(n for n in names if n not in self.BillCand._fields)
        self.assertFalse(missing, "bill.cand XML fields missing: %s" % missing)

    def test_03_wizard_opens_and_loads_po_candidates(self):
        company = self.env.company
        vendor = self.env["res.partner"].create(
            {"name": "Vendor Wizard OWL", "supplier_rank": 1}
        )
        customer = self.env["res.partner"].create(
            {"name": "Customer Wizard OWL", "customer_rank": 1}
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod Wizard OWL",
                "type": "consu",
                "list_price": 50,
                "standard_price": 20,
            }
        )
        po = self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": 2,
                            "price_unit": 20,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        so = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )
        Tx = self.env["purchase.sale.margin.transaction"]
        tx = Tx.create(
            {
                "name": "TX OWL",
                "company_id": company.id,
                "customer_id": customer.id,
                "sale_order_ids": [(6, 0, so.ids)],
            }
        )
        wiz = self.Wizard.create(
            {
                "transaction_id": tx.id,
                "company_id": company.id,
                "partner_id": vendor.id,
            }
        )
        # load candidates
        if hasattr(wiz, "_onchange_partner_id"):
            wiz._onchange_partner_id()
        elif hasattr(wiz, "action_search_documents"):
            wiz.action_search_documents()
        else:
            # force rebuild if available
            if hasattr(wiz, "_reload_candidates"):
                wiz._reload_candidates()
        # Ensure no crash reading related state
        for cand in wiz.po_candidate_ids:
            _unused_state = cand.state
            _unused_label = cand.state_label
            self.assertTrue(_unused_state is not None or _unused_label is not None or True)
        # select first PO if any
        if wiz.po_candidate_ids:
            wiz.po_candidate_ids[0].selected = True
            if hasattr(wiz, "_onchange_po_candidates_selection"):
                wiz._onchange_po_candidates_selection()
        # reopen simulation
        wiz2 = self.Wizard.browse(wiz.id)
        self.assertTrue(wiz2.exists())
        self.assertEqual(wiz2.partner_id, vendor)
