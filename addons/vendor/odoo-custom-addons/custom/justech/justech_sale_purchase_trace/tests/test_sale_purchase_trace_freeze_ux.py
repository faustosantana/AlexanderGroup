# -*- coding: utf-8 -*-
"""UX freeze: unique Compras smart button + Relacionar OC without SO save."""
from lxml import etree
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "justech_sale_purchase_trace")
class TestSalePurchaseTraceFreezeUx(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Freeze UX", "customer_rank": 1}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Proveedor Freeze UX", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Freeze UX",
                "type": "consu",
                "is_storable": True,
                "purchase_ok": True,
                "sale_ok": True,
                "list_price": 100,
                "standard_price": 50,
            }
        )

    def _so(self, qty=4):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )

    def _visible_stat_buttons(self, tree, name):
        visible = []
        for btn in tree.xpath("//button[@name='%s']" % name):
            inv = (btn.get("invisible") or "").strip()
            if inv in ("1", "True", "true"):
                continue
            visible.append(btn)
        return visible

    def test_form_has_single_compras_stat_button(self):
        views = self.env["sale.order"].get_views([(False, "form")])
        arch = views["views"]["form"]["arch"]
        tree = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
        native = self._visible_stat_buttons(tree, "action_view_purchase_orders")
        legacy = self._visible_stat_buttons(tree, "action_open_purchase_order")
        ours = tree.xpath("//button[@name='action_justech_open_purchases']")
        self.assertFalse(native, "Native sale_purchase Compras must stay hidden")
        self.assertFalse(legacy, "Legacy bi_convert Compras must stay hidden")
        self.assertEqual(len(ours), 1)

    def test_header_hides_generate_and_link_for_margins_hub(self):
        """SO header must not expose Trace purchase buttons (Margins hub owns UX)."""
        views = self.env["sale.order"].get_views([(False, "form")])
        arch = views["views"]["form"]["arch"]
        tree = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
        generate = [
            b
            for b in tree.xpath("//header//button[@name='action_justech_buy_pending']")
            if (b.get("invisible") or "").strip() not in ("1", "True", "true")
        ]
        link = [
            b
            for b in tree.xpath("//header//button[@name='action_justech_link_existing_po']")
            if (b.get("invisible") or "").strip() not in ("1", "True", "true")
        ]
        self.assertFalse(generate, "Generar orden de compra must stay hidden on SO header")
        self.assertFalse(link, "Relacionar compra existente must stay hidden on SO header")
        pending_label = tree.xpath(
            "//header//button[@string='Comprar pendientes']"
        )
        self.assertFalse(pending_label)
        legacy_create = [
            b
            for b in tree.xpath("//header//button")
            if (b.get("string") or "") == "Crear Orden de Compra"
            and (b.get("invisible") or "").strip() not in ("1", "True", "true")
        ]
        self.assertFalse(legacy_create)
        # When Margins hub is installed, it must be the only purchase entry on the header.
        margins = self.env["ir.module.module"].search(
            [("name", "=", "justech_purchase_sale_margin_control"), ("state", "=", "installed")],
            limit=1,
        )
        if margins:
            manage = [
                b
                for b in tree.xpath("//header//button[@name='action_manage_purchases']")
                if (b.get("invisible") or "").strip() not in ("1", "True", "true")
            ]
            self.assertEqual(len(manage), 1)
            self.assertEqual((manage[0].get("string") or ""), "Gestionar compras")


    def test_compras_opens_line_traceability(self):
        so = self._so()
        action = so.action_justech_open_purchases()
        self.assertEqual(action.get("res_model"), "sale.order.line")
        self.assertIn(("order_id", "=", so.id), action.get("domain") or [])

    def test_link_wizard_opens_on_saved_quote_without_payment_term(self):
        so = self._so()
        if "payment_term_id" in so._fields:
            so.payment_term_id = False
        action = so.action_justech_link_existing_po()
        self.assertEqual(action.get("res_model"), "justech.link.existing.po.wizard")
        self.assertEqual(action.get("target"), "new")
        self.assertEqual(action.get("context", {}).get("default_sale_order_id"), so.id)

    def test_link_wizard_requires_persisted_sale(self):
        so = self.env["sale.order"].new(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as err:
            so.action_justech_link_existing_po()
        self.assertIn("Guarde la cotización", str(err.exception))

    def test_cancel_link_wizard_does_not_change_sale(self):
        so = self._so()
        write_date = so.write_date
        wiz = self.env["justech.link.existing.po.wizard"].create(
            {"sale_order_id": so.id}
        )
        self.assertTrue(wiz.id)
        so.invalidate_recordset()
        self.assertEqual(so.write_date, write_date)
        self.assertEqual(so.state, "draft")

    def test_link_partial_and_full_still_work(self):
        so_a = self._so(6)
        so_b = self._so(4)
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 10,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )
        pol = po.order_line[0]
        pol.justech_link_to_sale_line(so_a.order_line[0], 6)
        self.assertAlmostEqual(pol.justech_qty_available_to_assign, 4)
        pol.justech_link_to_sale_line(so_b.order_line[0], 4)
        so_a.order_line.invalidate_recordset()
        so_b.order_line.invalidate_recordset()
        so_a.order_line._compute_justech_purchase_coverage()
        so_b.order_line._compute_justech_purchase_coverage()
        self.assertAlmostEqual(so_a.order_line.justech_qty_purchased, 6)
        self.assertAlmostEqual(so_b.order_line.justech_qty_purchased, 4)

    def test_buy_pending_still_creates_po(self):
        so = self._so(3)
        sol = so.order_line[0]
        sol._compute_justech_purchase_coverage()
        wiz = self.env["justech.buy.pending.wizard"].create(
            {
                "partner_id": self.vendor.id,
                "sale_order_id": so.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "product_id": sol.product_id.id,
                            "qty_sold": sol.justech_qty_sold,
                            "qty_pending": sol.justech_qty_pending_purchase,
                            "qty_to_buy": sol.justech_qty_pending_purchase,
                            "selected": True,
                            "snapshot_pending": sol.justech_qty_pending_purchase,
                        },
                    )
                ],
            }
        )
        action = wiz.action_create_purchase_order()
        po = self.env["purchase.order"].browse(action["res_id"])
        self.assertEqual(po.order_line.sale_line_id, sol)
        self.assertAlmostEqual(po.order_line.product_qty, 3)
