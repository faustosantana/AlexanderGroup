# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestJustechWarranty(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sales_group = cls.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
        if sales_group:
            cls.env.user.group_ids = [(4, sales_group.id)]
        cls.customer = cls.partner_a
        cls.product_wty = cls.env["product.product"].create(
            {"name": "Equipo con garantía", "type": "consu", "warranty_months": 12}
        )
        # RC6.2: los productos con "serial" ya no requieren stock instalado;
        # simulamos el atributo `tracking` sólo cuando el módulo stock está
        # disponible en el entorno de pruebas.
        serial_vals = {
            "name": "Equipo serie", "type": "consu", "warranty_months": 24,
        }
        if "tracking" in cls.env["product.product"]._fields:
            serial_vals["tracking"] = "serial"
        cls.product_serial = cls.env["product.product"].create(serial_vals)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _new_warranty(self, product, **vals):
        base = {
            "partner_id": self.customer.id,
            "product_id": product.id,
            "warranty_months": product.warranty_months,
        }
        base.update(vals)
        return self.env["justech.warranty"].create(base)

    def _new_sale_order(self, products, **order_vals):
        if not isinstance(products, list):
            products = [products]
        lines = [
            (0, 0, {"product_id": p.id, "product_uom_qty": 1}) for p in products
        ]
        vals = {"partner_id": self.customer.id, "order_line": lines}
        vals.update(order_vals)
        return self.env["sale.order"].create(vals)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def test_date_end_computation(self):
        warranty = self._new_warranty(
            self.product_wty, date_start=fields.Date.to_date("2026-01-15")
        )
        self.assertEqual(warranty.date_end, fields.Date.to_date("2027-01-15"))
        self.assertTrue(warranty.name.startswith("GAR/"))

    def test_serial_pending_when_activating_without_units(self):
        warranty = self._new_warranty(self.product_serial)
        self.assertEqual(warranty.state, "draft")
        warranty.action_activate()
        # RC6.2: sin unidades ni serial → queda pendiente de serial.
        self.assertEqual(warranty.state, "pending_serial")

    def test_cron_expires_active(self):
        warranty = self._new_warranty(
            self.product_wty,
            warranty_months=1,
            date_start=fields.Date.context_today(self.env.user) - relativedelta(months=2),
            state="active",
        )
        self.env["justech.warranty"]._cron_expire_warranties()
        self.assertEqual(warranty.state, "expired")

    def test_config_catalogs_loaded(self):
        self.assertTrue(
            self.env.ref("justech_warranty.warranty_type_store", raise_if_not_found=False)
        )
        self.assertTrue(
            self.env.ref("justech_warranty.claim_reason_factory", raise_if_not_found=False)
        )

    def test_type_onchange_sets_kind_and_months(self):
        wty_type = self.env.ref("justech_warranty.warranty_type_extended")
        with Form(self.env["justech.warranty"]) as form:
            form.partner_id = self.customer
            form.product_id = self.product_wty
            form.warranty_months = 0
            form.type_id = wty_type
            self.assertEqual(form.warranty_type, "extended")
            self.assertEqual(form.warranty_months, wty_type.default_months)

    def test_company_default_terms_applied(self):
        self.env.company.justech_warranty_default_terms = "Términos estándar Justech"
        warranty = self._new_warranty(self.product_wty)
        self.assertEqual(warranty.terms, "Términos estándar Justech")

    def test_vendor_coverage_gap(self):
        warranty = self._new_warranty(
            self.product_wty,
            warranty_months=24,
            vendor_warranty_months=12,
        )
        # gap = client (24) - vendor (12) = 12 meses
        self.assertEqual(warranty.coverage_gap_months, 12)

    # ------------------------------------------------------------------
    # Claim
    # ------------------------------------------------------------------
    def test_claim_resolution_sets_warranty_claimed_when_no_units(self):
        warranty = self._new_warranty(self.product_wty, state="active")
        claim = self.env["justech.warranty.claim"].create(
            {"warranty_id": warranty.id, "description": "No enciende"}
        )
        self.assertTrue(claim.name.startswith("RMA/"))
        self.assertEqual(claim.partner_id, self.customer)
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertEqual(warranty.state, "claimed")

    def test_claim_reason_assignable(self):
        reason = self.env.ref("justech_warranty.claim_reason_factory")
        warranty = self._new_warranty(self.product_wty, state="active")
        claim = self.env["justech.warranty.claim"].create(
            {
                "warranty_id": warranty.id,
                "description": "No enciende",
                "reason_id": reason.id,
            }
        )
        self.assertEqual(claim.reason_id, reason)

    # ------------------------------------------------------------------
    # Invoice → warranty + units
    # ------------------------------------------------------------------
    def test_warranty_generated_from_invoice(self):
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=True
        )
        warranties = self.env["justech.warranty"].search([("invoice_id", "=", invoice.id)])
        self.assertEqual(len(warranties), 1)
        self.assertEqual(warranties.state, "active")
        self.assertEqual(warranties.warranty_months, 12)
        # Cada garantía tiene al menos 1 unidad (qty=1 en init_invoice)
        self.assertEqual(len(warranties.unit_ids), 1)
        # Idempotente: no duplica al re-generar.
        invoice._generate_warranties()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_id", "=", invoice.id)]), 1
        )
        self.assertEqual(len(warranties.unit_ids), 1)

    def test_multi_unit_generation(self):
        """qty 3 en la línea → 3 unidades de garantía independientes."""
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_wty
        )
        line.quantity = 3
        line.warranty_expected_units = 3
        invoice.action_post()
        warranty = self.env["justech.warranty"].search(
            [("invoice_line_id", "=", line.id)]
        )
        self.assertEqual(len(warranty.unit_ids), 3)
        numbers = warranty.unit_ids.mapped("unit_number")
        self.assertEqual(sorted(numbers), [1, 2, 3])

    def test_planned_serials_populate_units(self):
        """Seriales pre-cargados en la línea deben crear unidades activas."""
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_wty
        )
        line.quantity = 3
        line.warranty_expected_units = 3
        line.warranty_planned_serials = "SN-A\nSN-B\nSN-C"
        invoice.action_post()
        warranty = self.env["justech.warranty"].search(
            [("invoice_line_id", "=", line.id)]
        )
        serials = sorted(warranty.unit_ids.mapped("serial_manufacturer"))
        self.assertEqual(serials, ["SN-A", "SN-B", "SN-C"])
        self.assertTrue(all(u.state == "active" for u in warranty.unit_ids))

    def test_no_warranty_for_line_without_config(self):
        cable = self.env["product.product"].create(
            {"name": "Cable sin garantía", "type": "consu", "warranty_months": 0}
        )
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=cable, post=True
        )
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_id", "=", invoice.id)]), 0
        )

    def test_per_line_warranty_generated(self):
        invoice = self.init_invoice(
            "out_invoice",
            partner=self.customer,
            products=[self.product_wty, self.product_serial],
            post=False,
        )
        invoice.action_post()
        warranties = self.env["justech.warranty"].search([("invoice_id", "=", invoice.id)])
        self.assertEqual(len(warranties), 2)
        by_prod = {w.product_id: w for w in warranties}
        self.assertEqual(by_prod[self.product_wty].warranty_months, 12)
        self.assertEqual(by_prod[self.product_serial].warranty_months, 24)
        self.assertEqual(
            by_prod[self.product_wty].invoice_line_id.product_id, self.product_wty
        )

    def test_line_override_before_post(self):
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product_wty)
        line.warranty_months = 6
        invoice.action_post()
        warranty = self.env["justech.warranty"].search([("invoice_line_id", "=", line.id)])
        self.assertEqual(warranty.warranty_months, 6)

    def test_line_disable_warranty(self):
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product_wty)
        line.warranty_apply = False
        invoice.action_post()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_line_id", "=", line.id)]), 0
        )

    def test_serial_manufacturer_unique_per_company(self):
        """Dos unidades con el mismo serial en la misma compañía → error."""
        warranty = self._new_warranty(self.product_wty, state="active")
        self.env["justech.warranty.unit"].create(
            {
                "warranty_id": warranty.id,
                "product_id": self.product_wty.id,
                "partner_id": self.customer.id,
                "serial_manufacturer": "SN-UNIQUE-1",
                "state": "active",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["justech.warranty.unit"].create(
                {
                    "warranty_id": warranty.id,
                    "product_id": self.product_wty.id,
                    "partner_id": self.customer.id,
                    "serial_manufacturer": "SN-UNIQUE-1",
                    "state": "active",
                }
            )

    def test_partial_claim_by_unit(self):
        """Reclamo sobre 1 de 3 unidades: header sigue activa."""
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_wty
        )
        line.quantity = 3
        line.warranty_expected_units = 3
        line.warranty_planned_serials = "SN-1\nSN-2\nSN-3"
        invoice.action_post()
        warranty = self.env["justech.warranty"].search(
            [("invoice_line_id", "=", line.id)]
        )
        self.assertEqual(warranty.state, "active")
        target_unit = warranty.unit_ids.sorted("unit_number")[0]
        claim = self.env["justech.warranty.claim"].create(
            {
                "warranty_id": warranty.id,
                "unit_ids": [(6, 0, target_unit.ids)],
                "description": "Falla la unidad SN-1",
            }
        )
        claim.action_resolve()
        self.assertEqual(target_unit.state, "claimed")
        # Header no cambia porque otras unidades siguen activas
        self.assertEqual(warranty.state, "active")

    def test_unit_coverage_gap_and_risk(self):
        unit = self.env["justech.warranty.unit"].create(
            {
                "product_id": self.product_wty.id,
                "partner_id": self.customer.id,
                "customer_warranty_months": 24,
                "vendor_warranty_months": 12,
                "customer_date_start": fields.Date.today(),
                "vendor_date_start": fields.Date.today(),
            }
        )
        self.assertEqual(unit.coverage_gap_months, 12)
        self.assertEqual(unit.coverage_risk, "high")

    # ------------------------------------------------------------------
    # Sale.order.line
    # ------------------------------------------------------------------
    def test_sale_line_defaults_from_product(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line.filtered(lambda l: l.product_id == self.product_wty)
        self.assertTrue(line.warranty_apply)
        self.assertEqual(line.warranty_months, 12)
        # RC6.2: expected_units auto = 1
        self.assertEqual(line.warranty_expected_units, 1)

    def test_sale_line_expected_units_follows_qty(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        line.product_uom_qty = 5
        # onchange asincrono: forzamos la ejecución
        line._onchange_product_uom_qty_warranty()
        self.assertGreaterEqual(line.warranty_expected_units, 5)

    def test_sale_line_warranty_fields_present(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        wty_fields = {f for f in line._fields if f.startswith("warranty_")}
        self.assertIn("warranty_expected_units", wty_fields)
        self.assertIn("warranty_planned_serials", wty_fields)
        self.assertIn("warranty_vendor_id", wty_fields)
        self.assertIn("warranty_units_label", wty_fields)
        self.assertIn("warranty_unit_ids", wty_fields)

    def test_sale_line_passes_to_invoice_line(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        line.warranty_months = 6
        line.warranty_notes = "Nota cotización"
        line.warranty_planned_serials = "SN-X"
        wty_type = self.env.ref("justech_warranty.warranty_type_extended")
        line.warranty_type_id = wty_type
        order.action_confirm()
        invoice = order._create_invoices()
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_wty
        )
        self.assertTrue(inv_line.warranty_apply)
        self.assertEqual(inv_line.warranty_months, 6)
        self.assertEqual(inv_line.warranty_type_id, wty_type)
        self.assertEqual(inv_line.warranty_notes, "Nota cotización")
        self.assertEqual(inv_line.warranty_planned_serials, "SN-X")

    def test_so_confirm_does_not_create_warranty(self):
        order = self._new_sale_order([self.product_wty, self.product_serial])
        order.action_confirm()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("sale_order_id", "=", order.id)]), 0
        )
        invoice = order._create_invoices()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_id", "in", invoice.ids)]), 0
        )
        invoice.action_post()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_id", "in", invoice.ids)]), 2
        )

    # ------------------------------------------------------------------
    # Wizard
    # ------------------------------------------------------------------
    def test_warranty_config_wizard_saved_line(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "sale.order.line",
                "line_id": line.id,
                "warranty_apply": True,
                "warranty_months": 6,
                "warranty_type_id": self.env.ref("justech_warranty.warranty_type_extended").id,
                "warranty_notes": "Condición especial demo",
                "warranty_expected_units": 2,
                "warranty_planned_serials": "SN-DEMO-1\nSN-DEMO-2",
            }
        )
        wizard.action_apply()
        self.assertEqual(line.warranty_months, 6)
        self.assertEqual(line.warranty_notes, "Condición especial demo")
        self.assertEqual(line.warranty_expected_units, 2)
        self.assertIn("6m", line.warranty_summary)

    def test_warranty_config_wizard_draft_line_returns_infos(self):
        """`action_apply` sobre `line_id=0` no escribe pero devuelve infos."""
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "sale.order.line",
                "line_id": 0,
                "warranty_apply": True,
                "warranty_months": 9,
                "warranty_expected_units": 3,
                "warranty_planned_serials": "S1\nS2",
            }
        )
        action = wizard.action_apply()
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertIn("infos", action)
        self.assertTrue(action["infos"].get("applied"))
        vals = action["infos"]["vals"]
        self.assertTrue(vals["warranty_apply"])
        self.assertEqual(vals["warranty_months"], 9)
        self.assertEqual(vals["warranty_expected_units"], 3)
        self.assertEqual(vals["warranty_planned_serials"], "S1\nS2")

    def test_warranty_config_wizard_get_line_values(self):
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "sale.order.line",
                "line_id": 0,
                "warranty_apply": True,
                "warranty_months": 12,
                "warranty_expected_units": 1,
            }
        )
        vals = wizard.get_line_values()
        self.assertTrue(vals["warranty_apply"])
        self.assertEqual(vals["warranty_months"], 12)

    def test_warranty_wizard_action_structure(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        line.write({"warranty_apply": False})
        action = line.action_open_warranty_config_wizard()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "justech.warranty.line.config.wizard")
        self.assertTrue(action.get("views"))
        self.assertEqual(action.get("target"), "new")

    def test_warranty_config_btn_ready_for_new_line(self):
        """La línea no guardada (NewId) debe exponer marker 'draft' cuando hay producto."""
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.customer
            with form.order_line.new() as line_form:
                line_form.product_id = self.product_wty
                self.assertEqual(line_form.warranty_config_btn, "draft")

    def test_warranty_status_on_line(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        self.assertEqual(line.warranty_status, "configured")
        line.write({"warranty_apply": False})
        self.assertEqual(line.warranty_status, "none")
        line.write({"warranty_apply": True})
        line.write({"warranty_months": 0})
        self.assertEqual(line.warranty_status, "pending")

    def test_warranty_toggle_applies_product_defaults(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        line.write({"warranty_apply": False, "warranty_months": 0, "warranty_type_id": False})
        line.write({"warranty_apply": True})
        self.assertEqual(line.warranty_months, 12)

    def test_warranty_wizard_disable_clears_line(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "sale.order.line",
                "line_id": line.id,
                "warranty_apply": False,
                "warranty_months": 12,
            }
        )
        wizard.action_apply()
        self.assertFalse(line.warranty_apply)
        self.assertEqual(line.warranty_months, 0)
        self.assertFalse(line.warranty_summary)

    def test_quotation_warranty_flow_end_to_end(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "sale.order.line",
                "line_id": line.id,
                "warranty_apply": True,
                "warranty_months": 18,
                "warranty_type_id": self.env.ref("justech_warranty.warranty_type_extended").id,
            }
        )
        wizard.action_apply()
        self.assertIn("18m", line.warranty_summary)
        line.write({"warranty_apply": False})
        self.assertFalse(line.warranty_summary)
        order.action_confirm()
        invoice = order._create_invoices()
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product_wty
        )
        self.assertFalse(inv_line.warranty_apply)
        invoice.action_post()
        self.assertEqual(
            self.env["justech.warranty"].search_count([("invoice_id", "=", invoice.id)]), 0
        )

    def test_direct_invoice_warranty_flow_end_to_end(self):
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product_wty)
        wizard = self.env["justech.warranty.line.config.wizard"].create(
            {
                "line_model": "account.move.line",
                "line_id": line.id,
                "warranty_apply": True,
                "warranty_months": 9,
                "warranty_type_id": self.env.ref("justech_warranty.warranty_type_store").id,
            }
        )
        wizard.action_apply()
        self.assertEqual(line.warranty_months, 9)
        invoice.action_post()
        warranties = self.env["justech.warranty"].search([("invoice_id", "=", invoice.id)])
        self.assertEqual(len(warranties), 1)
        self.assertEqual(warranties.warranty_months, 9)

    # ------------------------------------------------------------------
    # Account.move.line legacy compat
    # ------------------------------------------------------------------
    def test_line_defaults_from_product(self):
        invoice = self.init_invoice(
            "out_invoice", partner=self.customer, products=self.product_wty, post=False
        )
        line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.product_wty)
        self.assertTrue(line.warranty_apply)
        self.assertEqual(line.warranty_months, 12)

    def test_warranty_summary_compact(self):
        order = self._new_sale_order(self.product_wty)
        line = order.order_line[:1]
        wty_type = self.env.ref("justech_warranty.warranty_type_store")
        line.write({"warranty_type_id": wty_type.id})
        self.assertIn("12m", line.warranty_summary)
        line.write({"warranty_apply": False})
        self.assertFalse(line.warranty_summary)

    def test_warranty_create_with_apply_loads_defaults(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_wty.id,
                            "product_uom_qty": 1,
                            "warranty_apply": True,
                        },
                    )
                ],
            }
        )
        line = order.order_line[:1]
        self.assertEqual(line.warranty_months, 12)
        self.assertIn("12m", line.warranty_summary)
