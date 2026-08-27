# -*- coding: utf-8 -*-
"""19.0.7.0.0 — Generador UAT + limpieza de fixtures Sprint 6."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseSaleMarginUatWizard(models.TransientModel):
    _name = "purchase.sale.margin.uat.wizard"
    _description = "Generar casos UAT-MARGIN-FINAL (transacciones reales)"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    result_log = fields.Text(readonly=True)
    created_transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction",
        "psm_uat_wiz_tx_rel",
        "wizard_id",
        "transaction_id",
        string="Transacciones creadas",
        readonly=True,
    )

    def action_generate_cases(self):
        self.ensure_one()
        log = []
        txs = self.env["purchase.sale.margin.transaction"]

        # Case 1: Incabide — 1 SO, 2 PO Omega, 2 vendor bills, 1 customer invoice
        txs |= self._case_incabide(log)
        # Case 2: one sale, five vendor bills
        txs |= self._case_five_vendor_bills(log)
        # Case 3: administrative purchase
        txs |= self._case_admin_purchase(log)
        # Case 4: purchase without sale
        txs |= self._case_purchase_no_sale(log)
        # Case 5: sale without cost
        txs |= self._case_sale_no_cost(log)
        # Case 6: three vendors
        txs |= self._case_three_vendors(log)

        self.write(
            {
                "result_log": "\n".join(log),
                "created_transaction_ids": [(6, 0, txs.ids)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _product(self, name, price, cost):
        return self.env["product.product"].create(
            {
                "name": "UAT-MARGIN-FINAL %s" % name,
                "type": "consu",
                "list_price": price,
                "standard_price": cost,
            }
        )

    def _partner(self, name, supplier=False, customer=False):
        return self.env["res.partner"].create(
            {
                "name": name,
                "supplier_rank": 1 if supplier else 0,
                "customer_rank": 1 if customer else 0,
                "company_id": False,
            }
        )

    def _so(self, customer, product, qty, price, name_suffix=""):
        so = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "company_id": self.company_id.id,
                "client_order_ref": "UAT-MARGIN-FINAL-%s" % name_suffix,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        so.action_confirm()
        return so

    def _po(self, vendor, product, qty, price, origin=None):
        po = self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "company_id": self.company_id.id,
                "origin": origin or False,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _bill(self, vendor, product, qty, price, ref, po=None):
        Move = self.env["account.move"]
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company_id.id)], limit=1
        )
        if not journal:
            raise UserError(_("No hay diario de compras en la compañía."))
        vals = {
            "move_type": "in_invoice",
            "partner_id": vendor.id,
            "company_id": self.company_id.id,
            "journal_id": journal.id,
            "invoice_date": fields.Date.context_today(self),
            "ref": ref,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": qty,
                        "price_unit": price,
                        "name": product.display_name,
                        "purchase_line_id": po.order_line[:1].id if po else False,
                    },
                )
            ],
        }
        move = Move.create(vals)
        return move

    def _invoice(self, customer, product, qty, price, so=None):
        Move = self.env["account.move"]
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company_id.id)], limit=1
        )
        if not journal:
            raise UserError(_("No hay diario de ventas en la compañía."))
        line_vals = {
            "product_id": product.id,
            "quantity": qty,
            "price_unit": price,
            "name": product.display_name,
        }
        if so and so.order_line:
            line_vals["sale_line_ids"] = [(6, 0, so.order_line.ids)]
        move = Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "company_id": self.company_id.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.context_today(self),
                "ref": "UAT-MARGIN-FINAL-INV",
                "invoice_line_ids": [(0, 0, line_vals)],
            }
        )
        return move

    def _tx(self, **vals):
        vals.setdefault("company_id", self.company_id.id)
        vals.setdefault("is_uat_fixture", True)
        vals.setdefault("link_mode", "automatic")
        vals.setdefault("source", "auto_detected")
        vals.setdefault("state", "pending_review")
        return self.env["purchase.sale.margin.transaction"].create(vals)

    def _case_incabide(self, log):
        customer = self._partner("UAT-MARGIN-FINAL Incabide", customer=True)
        vendor = self._partner("UAT-MARGIN-FINAL Omega", supplier=True)
        p1 = self._product("Laptop Incabide", 25000, 18000)
        p2 = self._product("Teclado Incabide", 1500, 900)
        so = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "company_id": self.company_id.id,
                "client_order_ref": "UAT-MARGIN-FINAL-INCABIDE",
                "order_line": [
                    (0, 0, {"product_id": p1.id, "product_uom_qty": 1, "price_unit": 25000}),
                    (0, 0, {"product_id": p2.id, "product_uom_qty": 3, "price_unit": 1500}),
                ],
            }
        )
        so.action_confirm()
        po1 = self._po(vendor, p1, 1, 18000, origin=so.name)
        po2 = self._po(vendor, p2, 3, 900, origin=so.name)
        bill1 = self._bill(vendor, p1, 1, 18000, "UAT-MARGIN-FINAL-NCF-OMEGA-1", po1)
        bill2 = self._bill(vendor, p2, 3, 900, "UAT-MARGIN-FINAL-NCF-OMEGA-2", po2)
        inv = self._invoice(customer, p1, 1, 25000, so)
        tx = self.env["purchase.sale.margin.transaction"].search(
            [("sale_order_ids", "in", so.id)], limit=1
        )
        vals = {
            "is_uat_fixture": True,
            "project_name": "Incabide",
            "customer_id": customer.id,
            "purchase_order_ids": [(6, 0, [po1.id, po2.id])],
            "vendor_bill_ids": [(6, 0, [bill1.id, bill2.id])],
            "customer_invoice_ids": [(6, 0, [inv.id])],
            "supplier_ids": [(6, 0, [vendor.id])],
            "link_mode": "automatic",
        }
        if tx:
            tx.write(vals)
        else:
            vals.update(
                {
                    "name": "Incabide",
                    "sale_order_ids": [(6, 0, [so.id])],
                    "company_id": self.company_id.id,
                    "source": "auto_detected",
                    "state": "pending_review",
                }
            )
            tx = self.env["purchase.sale.margin.transaction"].create(vals)
        log.append(
            "Caso 1 Incabide: TX %s | SO %s | PO %s,%s | Bills 2 | INV 1"
            % (tx.transaction_number, so.name, po1.name, po2.name)
        )
        return tx

    def _case_five_vendor_bills(self, log):
        customer = self._partner("UAT-MARGIN-FINAL Cliente 5FP", customer=True)
        vendor = self._partner("UAT-MARGIN-FINAL Proveedor 5FP", supplier=True)
        product = self._product("Kit 5FP", 10000, 1200)
        so = self._so(customer, product, 1, 10000, "5FP")
        bills = self.env["account.move"]
        pos = self.env["purchase.order"]
        for i in range(5):
            po = self._po(vendor, product, 1, 1200 + i * 10, origin=so.name)
            pos |= po
            bills |= self._bill(vendor, product, 1, 1200 + i * 10, "UAT-MARGIN-FINAL-5FP-%s" % (i + 1), po)
        inv = self._invoice(customer, product, 1, 10000, so)
        tx = self.env["purchase.sale.margin.transaction"].search(
            [("sale_order_ids", "in", so.id)], limit=1
        )
        if tx:
            tx.write(
                {
                    "is_uat_fixture": True,
                    "project_name": "Cinco facturas proveedor",
                    "purchase_order_ids": [(6, 0, pos.ids)],
                    "vendor_bill_ids": [(6, 0, bills.ids)],
                    "customer_invoice_ids": [(4, inv.id)],
                    "supplier_ids": [(4, vendor.id)],
                }
            )
        else:
            tx = self._tx(
                name="5 FP",
                project_name="Cinco facturas proveedor",
                customer_id=customer.id,
                sale_order_ids=[(6, 0, [so.id])],
                purchase_order_ids=[(6, 0, pos.ids)],
                vendor_bill_ids=[(6, 0, bills.ids)],
                customer_invoice_ids=[(6, 0, [inv.id])],
                supplier_ids=[(6, 0, [vendor.id])],
            )
        log.append("Caso 2: TX %s con %s facturas proveedor" % (tx.transaction_number, len(bills)))
        return tx

    def _case_admin_purchase(self, log):
        vendor = self._partner("UAT-MARGIN-FINAL Admin Vendor", supplier=True)
        product = self._product("Gasto admin", 0, 5000)
        po = self._po(vendor, product, 1, 5000)
        bill = self._bill(vendor, product, 1, 5000, "UAT-MARGIN-FINAL-ADMIN")
        tx = self._tx(
            name="Admin",
            project_name="Compra administrativa",
            transaction_type="administrative",
            purchase_order_ids=[(6, 0, [po.id])],
            vendor_bill_ids=[(6, 0, [bill.id])],
            supplier_ids=[(6, 0, [vendor.id])],
            link_mode="historical",
        )
        log.append("Caso 3 admin: TX %s" % tx.transaction_number)
        return tx

    def _case_purchase_no_sale(self, log):
        vendor = self._partner("UAT-MARGIN-FINAL CompraSinVenta", supplier=True)
        product = self._product("Inventario", 0, 3200)
        po = self._po(vendor, product, 2, 1600)
        bill = self._bill(vendor, product, 2, 1600, "UAT-MARGIN-FINAL-NOSALE", po)
        tx = self._tx(
            name="Sin venta",
            project_name="Compra sin venta",
            purchase_order_ids=[(6, 0, [po.id])],
            vendor_bill_ids=[(6, 0, [bill.id])],
            supplier_ids=[(6, 0, [vendor.id])],
            link_mode="historical",
        )
        log.append("Caso 4 compra sin venta: TX %s" % tx.transaction_number)
        return tx

    def _case_sale_no_cost(self, log):
        customer = self._partner("UAT-MARGIN-FINAL VentaSinCosto", customer=True)
        product = self._product("Servicio", 8000, 0)
        so = self._so(customer, product, 1, 8000, "NOSCOST")
        inv = self._invoice(customer, product, 1, 8000, so)
        tx = self._tx(
            name="Sin costo",
            project_name="Venta sin costos",
            customer_id=customer.id,
            sale_order_ids=[(6, 0, [so.id])],
            customer_invoice_ids=[(6, 0, [inv.id])],
            link_mode="historical",
        )
        log.append("Caso 5 venta sin costo: TX %s" % tx.transaction_number)
        return tx

    def _case_three_vendors(self, log):
        customer = self._partner("UAT-MARGIN-FINAL MultiVendor Cliente", customer=True)
        v1 = self._partner("UAT-MARGIN-FINAL CECOMSA", supplier=True)
        v2 = self._partner("UAT-MARGIN-FINAL Omega Multi", supplier=True)
        v3 = self._partner("UAT-MARGIN-FINAL TechParts", supplier=True)
        p1 = self._product("Monitor", 8000, 5500)
        p2 = self._product("Toner", 3000, 1800)
        p3 = self._product("Cable", 500, 200)
        so = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "company_id": self.company_id.id,
                "client_order_ref": "UAT-MARGIN-FINAL-MULTI",
                "order_line": [
                    (0, 0, {"product_id": p1.id, "product_uom_qty": 1, "price_unit": 8000}),
                    (0, 0, {"product_id": p2.id, "product_uom_qty": 2, "price_unit": 1500}),
                    (0, 0, {"product_id": p3.id, "product_uom_qty": 5, "price_unit": 100}),
                ],
            }
        )
        so.action_confirm()
        po1 = self._po(v1, p1, 1, 5500, origin=so.name)
        po2 = self._po(v2, p2, 2, 900, origin=so.name)
        po3 = self._po(v3, p3, 5, 40, origin=so.name)
        b1 = self._bill(v1, p1, 1, 5500, "UAT-MARGIN-FINAL-MV-1", po1)
        b2 = self._bill(v2, p2, 2, 900, "UAT-MARGIN-FINAL-MV-2", po2)
        b3 = self._bill(v3, p3, 5, 40, "UAT-MARGIN-FINAL-MV-3", po3)
        inv = self._invoice(customer, p1, 1, 8000, so)
        tx = self.env["purchase.sale.margin.transaction"].search(
            [("sale_order_ids", "in", so.id)], limit=1
        )
        vals = {
            "is_uat_fixture": True,
            "project_name": "Tres proveedores",
            "customer_id": customer.id,
            "purchase_order_ids": [(6, 0, [po1.id, po2.id, po3.id])],
            "vendor_bill_ids": [(6, 0, [b1.id, b2.id, b3.id])],
            "customer_invoice_ids": [(6, 0, [inv.id])],
            "supplier_ids": [(6, 0, [v1.id, v2.id, v3.id])],
            "link_mode": "automatic",
        }
        if tx:
            tx.write(vals)
        else:
            vals.update(
                {
                    "name": "Multi vendor",
                    "sale_order_ids": [(6, 0, [so.id])],
                    "company_id": self.company_id.id,
                    "source": "auto_detected",
                    "state": "pending_review",
                }
            )
            tx = self.env["purchase.sale.margin.transaction"].create(vals)
        log.append(
            "Caso 6 tres proveedores: TX %s | proveedores=%s"
            % (tx.transaction_number, len(tx.supplier_ids))
        )
        return tx


class PurchaseSaleMarginUatCleanupWizard(models.TransientModel):
    _name = "purchase.sale.margin.uat.cleanup.wizard"
    _description = "Limpiar fixtures UAT-MARGIN-FINAL"

    confirm = fields.Boolean(
        string="Confirmo eliminar solo fixtures UAT-MARGIN-FINAL",
        required=True,
    )
    result_log = fields.Text(readonly=True)

    def action_cleanup(self):
        self.ensure_one()
        if not self.confirm:
            raise UserError(_("Marque la confirmación para continuar."))
        Tx = self.env["purchase.sale.margin.transaction"]
        txs = Tx.search([("is_uat_fixture", "=", True)])
        moves = txs.mapped("vendor_bill_ids") | txs.mapped("customer_invoice_ids")
        pos = txs.mapped("purchase_order_ids")
        sos = txs.mapped("sale_order_ids")
        partners = self.env["res.partner"].search([("name", "like", "UAT-MARGIN-FINAL%")])
        products = self.env["product.product"].search([("name", "like", "UAT-MARGIN-FINAL%")])

        # Cancel drafts / delete safe
        draft_moves = moves.filtered(lambda m: m.state == "draft")
        draft_moves.unlink()
        # Posted moves: cancel if possible else leave and detach
        for m in moves - draft_moves:
            try:
                if m.state == "posted":
                    m.button_draft()
                    m.button_cancel()
                m.unlink()
            except Exception:  # noqa: BLE001
                _logger.warning("No se pudo borrar move %s", m.id)

        count_tx = len(txs)
        txs.unlink()

        for po in pos:
            try:
                if po.state not in ("cancel", "draft"):
                    po.button_cancel()
                po.unlink()
            except Exception:  # noqa: BLE001
                _logger.warning("No se pudo borrar PO %s", po.id)
        for so in sos:
            try:
                if so.state not in ("cancel", "draft"):
                    so._action_cancel()
                so.unlink()
            except Exception:  # noqa: BLE001
                _logger.warning("No se pudo borrar SO %s", so.id)

        try:
            products.write({"active": False})
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudieron archivar productos UAT")
        try:
            partners.write({"active": False})
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudieron archivar partners UAT")
        self.result_log = _(
            "Eliminadas %s transacciones UAT. Productos/partners UAT-MARGIN-FINAL archivados."
        ) % count_tx
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
