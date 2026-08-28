# -*- coding: utf-8 -*-
"""Presentation-only checks for responsive purchase wizards (19.0.1.2.5)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseResponsiveWizards(TransactionCase):
    def test_buy_wizard_view_labels_and_class(self):
        view = self.env.ref(
            "justech_sale_purchase_trace.view_justech_buy_pending_wizard_form"
        )
        arch = view.arch_db or ""
        self.assertIn("o_justech_sp_buy_wizard", arch)
        self.assertIn('string="Empresa"', arch)
        self.assertIn('string="Inventario"', arch)
        self.assertIn('string="Pendiente"', arch)
        self.assertIn('string="A comprar"', arch)
        self.assertIn('string="Sel."', arch)

    def test_link_wizard_view_switches_and_class(self):
        view = self.env.ref(
            "justech_sale_purchase_trace.view_justech_link_existing_po_wizard_form"
        )
        arch = view.arch_db or ""
        self.assertIn("o_justech_sp_link_wizard", arch)
        self.assertIn('string="Empresa"', arch)
        self.assertIn('string="Disponible"', arch)
        self.assertIn('string="A relacionar"', arch)
        self.assertIn('string="NCF/e-CF"', arch)
        self.assertIn("document_type != 'purchase_order'", arch)
        self.assertIn("document_type != 'vendor_bill'", arch)

    def test_module_assets_include_scss(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_sale_purchase_trace")], limit=1
        )
        self.assertEqual(mod.latest_version, "19.0.1.2.7")
        manifest = self.env["ir.module.module"].get_module_info(
            "justech_sale_purchase_trace"
        )
        assets = (manifest or {}).get("assets", {}).get("web.assets_backend", [])
        self.assertTrue(
            any("purchase_wizards.scss" in (a or "") for a in assets),
            assets,
        )

    def test_ncf_display_field_present(self):
        self.assertIn(
            "ncf_display",
            self.env["justech.link.existing.bill.wizard.line"]._fields,
        )
