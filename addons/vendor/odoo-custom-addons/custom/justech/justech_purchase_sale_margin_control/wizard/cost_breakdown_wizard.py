# -*- coding: utf-8 -*-
"""Business-facing cost breakdown for a sale order (no technical IDs/confidence)."""
from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)


class PurchaseSaleCostBreakdownWizard(models.TransientModel):
    _name = "purchase.sale.cost.breakdown.wizard"
    _description = "Desglose de costos y márgenes (vista negocio)"

    sale_order_id = fields.Many2one("sale.order", required=True, readonly=True)
    currency_id = fields.Many2one(related="sale_order_id.currency_id", readonly=True)
    line_ids = fields.One2many(
        "purchase.sale.cost.breakdown.wizard.line",
        "wizard_id",
        string="Artículos",
        readonly=True,
    )
    total_cost = fields.Monetary(
        string="Total costo",
        currency_field="currency_id",
        readonly=True,
    )
    sale_untaxed = fields.Monetary(
        string="Venta sin ITBIS",
        currency_field="currency_id",
        readonly=True,
    )
    margin_amount = fields.Monetary(
        string="Margen",
        currency_field="currency_id",
        readonly=True,
    )
    margin_pct = fields.Float(string="Margen %", readonly=True)
    cost_origin = fields.Char(string="Origen del costo", readonly=True)

    @api.model
    def open_for_sale_order(self, sale_order):
        """Build wizard from live assignments and open form."""
        sale_order.ensure_one()
        alloc = LineAllocationService(self.env)
        for tx in sale_order.margin_transaction_ids:
            alloc.confirm_unequivocal_cost_relations(tx)

        rows = alloc.collect_live_assigned_cost_rows(sale_order)
        # Aggregate by sale line (one row per article)
        by_sol = {}
        for row in rows:
            sol = row["sale_line"]
            if not sol:
                continue
            key = sol.id
            if key not in by_sol:
                by_sol[key] = {
                    "sol": sol,
                    "qty": 0.0,
                    "cost": 0.0,
                    "pols": self.env["purchase.order.line"],
                    "bills": self.env["account.move"],
                }
            by_sol[key]["qty"] += row.get("assigned_qty") or 0.0
            by_sol[key]["cost"] += (row.get("real_cost") or 0.0) + (
                row.get("estimated_cost") or 0.0
            )
            pol = row.get("purchase_line")
            if pol:
                by_sol[key]["pols"] |= pol
                for aml in pol.invoice_lines:
                    move = aml.move_id
                    if (
                        move
                        and move.state == "posted"
                        and move.move_type in ("in_invoice", "in_refund")
                        and float_compare(aml.quantity or 0.0, 0.0, precision_digits=4) > 0
                    ):
                        by_sol[key]["bills"] |= move

        line_cmds = []
        for data in by_sol.values():
            sol = data["sol"]
            qty = data["qty"] or sol.product_uom_qty or 0.0
            cost = data["cost"]
            unit = (cost / qty) if qty else 0.0
            bill = data["bills"][:1]
            pol = data["pols"][:1]
            if bill:
                source = _("Factura proveedor")
                doc = bill
                doc_name = bill.display_name
            elif pol and pol.order_id:
                source = _("Orden de compra")
                doc = pol.order_id
                doc_name = pol.order_id.display_name
            else:
                source = _("Asignación")
                doc = False
                doc_name = ""
            line_cmds.append(
                (
                    0,
                    0,
                    {
                        "product_id": sol.product_id.id,
                        "sold_qty": sol.product_uom_qty,
                        "cost_qty": qty,
                        "unit_cost": unit,
                        "total_cost": cost,
                        "source_label": source,
                        "document_name": doc_name,
                        "purchase_order_id": pol.order_id.id if pol and pol.order_id else False,
                        "vendor_bill_id": bill.id if bill else False,
                    },
                )
            )

        total = sum(c[2]["total_cost"] for c in line_cmds)
        sale = sale_order.amount_untaxed or 0.0
        margin = sale - total
        pct = (margin / sale * 100.0) if sale else 0.0
        origin = sale_order.margin_control_cost_origin or ""

        wiz = self.create(
            {
                "sale_order_id": sale_order.id,
                "line_ids": line_cmds,
                "total_cost": total,
                "sale_untaxed": sale,
                "margin_amount": margin,
                "margin_pct": pct,
                "cost_origin": origin,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Costos y Márgenes"),
            "res_model": self._name,
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
            "context": {"create": False, "edit": False},
        }


class PurchaseSaleCostBreakdownWizardLine(models.TransientModel):
    _name = "purchase.sale.cost.breakdown.wizard.line"
    _description = "Línea desglose costos (vista negocio)"
    _order = "id"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.breakdown.wizard", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Artículo", readonly=True)
    sold_qty = fields.Float(string="Cantidad vendida", readonly=True)
    cost_qty = fields.Float(string="Cantidad costo", readonly=True)
    unit_cost = fields.Monetary(
        string="Costo unitario",
        currency_field="currency_id",
        readonly=True,
    )
    total_cost = fields.Monetary(
        string="Costo total",
        currency_field="currency_id",
        readonly=True,
    )
    source_label = fields.Char(string="Fuente", readonly=True)
    document_name = fields.Char(string="Documento", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", readonly=True)
    vendor_bill_id = fields.Many2one("account.move", readonly=True)
    currency_id = fields.Many2one(related="wizard_id.currency_id", readonly=True)

    def action_open_document(self):
        self.ensure_one()
        if self.vendor_bill_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Factura proveedor"),
                "res_model": "account.move",
                "res_id": self.vendor_bill_id.id,
                "view_mode": "form",
                "target": "current",
            }
        if self.purchase_order_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Orden de compra"),
                "res_model": "purchase.order",
                "res_id": self.purchase_order_id.id,
                "view_mode": "form",
                "target": "current",
            }
        return False
