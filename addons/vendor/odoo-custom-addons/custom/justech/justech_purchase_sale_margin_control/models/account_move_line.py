# -*- coding: utf-8 -*-
from odoo import api, fields, models

from . import margin_acl


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cost_allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation", "vendor_bill_line_id", string="Asignaciones (como costo)"
    )
    customer_allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation",
        "customer_invoice_line_id",
        string="Asignaciones (como venta)",
    )
    allocated_amount_total = fields.Monetary(
        string="Total asignado", compute="_compute_allocation_amounts", currency_field="currency_id"
    )
    unallocated_amount = fields.Monetary(
        string="Monto sin asignar", compute="_compute_allocation_amounts", currency_field="currency_id"
    )

    @api.depends("cost_allocation_ids.allocated_amount", "cost_allocation_ids.state", "price_subtotal")
    def _compute_allocation_amounts(self):
        Alloc = margin_acl.margin_cost_allocation(self.env)
        for rec in self:
            active = Alloc.search(
                [
                    ("vendor_bill_line_id", "=", rec.id),
                    ("state", "not in", ("cancelled", "excluded")),
                ]
            )
            allocated = sum(active.mapped("allocated_amount"))
            rec.allocated_amount_total = allocated
            rec.unallocated_amount = abs(rec.price_subtotal) - abs(allocated)
