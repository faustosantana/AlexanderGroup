# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.cost_link import COST_USAGE


class PurchaseSaleAllocateWizard(models.TransientModel):
    _name = "purchase.sale.allocate.wizard"
    _description = "Asignar costo de compra a venta(s)"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    vendor_bill_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de factura proveedor",
        domain="[('move_id.move_type', 'in', ('in_invoice', 'in_refund')), "
        "('display_type', '=', False)]",
    )
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de orden de compra"
    )
    currency_id = fields.Many2one(
        "res.currency", related="vendor_bill_line_id.currency_id", string="Moneda"
    )
    source_amount = fields.Monetary(
        string="Monto disponible", compute="_compute_source_amount", currency_field="currency_id"
    )
    line_ids = fields.One2many(
        "purchase.sale.allocate.wizard.line", "wizard_id", string="Distribución"
    )
    total_allocated = fields.Monetary(
        string="Total asignado", compute="_compute_totals", currency_field="currency_id"
    )
    remaining_amount = fields.Monetary(
        string="Remanente", compute="_compute_totals", currency_field="currency_id"
    )

    @api.depends("vendor_bill_line_id", "purchase_order_line_id")
    def _compute_source_amount(self):
        for rec in self:
            if rec.vendor_bill_line_id:
                rec.source_amount = abs(rec.vendor_bill_line_id.price_subtotal)
            elif rec.purchase_order_line_id:
                rec.source_amount = abs(rec.purchase_order_line_id.price_subtotal)
            else:
                rec.source_amount = 0.0

    @api.depends("line_ids.amount", "source_amount")
    def _compute_totals(self):
        for rec in self:
            rec.total_allocated = sum(rec.line_ids.mapped("amount"))
            rec.remaining_amount = rec.source_amount - rec.total_allocated

    @api.onchange("vendor_bill_line_id")
    def _onchange_vendor_bill_line_id(self):
        if self.vendor_bill_line_id and self.vendor_bill_line_id.purchase_line_id:
            self.purchase_order_line_id = self.vendor_bill_line_id.purchase_line_id

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Agregue al menos una línea de distribución."))
        if not self.vendor_bill_line_id and not self.purchase_order_line_id:
            raise UserError(_("Seleccione una línea de factura u orden de compra origen."))

        link = False
        if self.purchase_order_line_id:
            Trace = self.env["purchase.sale.trace.engine"]
            link = Trace.get_or_create_link_for_purchase_line(self.purchase_order_line_id)

        Allocation = self.env["purchase.sale.cost.allocation"]
        created = Allocation

        for line in self.line_ids:
            if not line.sale_order_id:
                raise UserError(_("Cada línea de distribución debe tener una orden de venta."))
            if line.sale_order_id.company_id != self.company_id:
                raise UserError(_("No se permiten asignaciones entre compañías distintas."))

            vals = {
                "link_id": link.id if link else False,
                "company_id": self.company_id.id,
                "vendor_bill_id": self.vendor_bill_line_id.move_id.id
                if self.vendor_bill_line_id
                else False,
                "vendor_bill_line_id": self.vendor_bill_line_id.id
                if self.vendor_bill_line_id
                else False,
                "purchase_order_id": self.purchase_order_line_id.order_id.id
                if self.purchase_order_line_id
                else False,
                "purchase_order_line_id": self.purchase_order_line_id.id
                if self.purchase_order_line_id
                else False,
                "sale_order_id": line.sale_order_id.id,
                "sale_order_line_id": line.sale_order_line_id.id,
                "partner_id": line.sale_order_id.partner_id.id,
                "supplier_id": self.vendor_bill_line_id.move_id.partner_id.id
                if self.vendor_bill_line_id
                else False,
                "product_id": (self.vendor_bill_line_id or self.purchase_order_line_id).product_id.id,
                "currency_id": self.currency_id.id or self.company_id.currency_id.id,
                "source_amount": self.source_amount,
                "allocated_amount": line.amount,
                "allocation_method": "manual",
                "cost_usage_type": line.cost_usage_type,
                "additional_cost_type": line.additional_cost_type,
                "source": "manual",
                "confidence": 100,
                "is_manual": True,
                "state": "confirmed",
                "confirmed_by_id": self.env.user.id,
                "confirmed_at": fields.Datetime.now(),
                "notes": line.notes,
            }
            created |= Allocation.create(vals)

        if link and len(self.line_ids.mapped("sale_order_id")) == 1:
            link.write(
                {
                    "sale_id": self.line_ids[0].sale_order_id.id,
                    "sale_line_id": self.line_ids[0].sale_order_line_id.id,
                    "link_source": "manual",
                    "is_manual": True,
                    "confidence": 100,
                    "state": "confirmed",
                }
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Asignaciones creadas"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }


class PurchaseSaleAllocateWizardLine(models.TransientModel):
    _name = "purchase.sale.allocate.wizard.line"
    _description = "Línea de distribución del asistente de asignación"

    wizard_id = fields.Many2one("purchase.sale.allocate.wizard", required=True, ondelete="cascade")
    sale_order_id = fields.Many2one("sale.order", string="Orden de venta", required=True)
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta",
        domain="[('order_id', '=', sale_order_id)]",
    )
    amount = fields.Monetary(string="Monto", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    cost_usage_type = fields.Selection(COST_USAGE, default="resale_direct", string="Clasificación")
    additional_cost_type = fields.Selection(
        [
            ("none", "Ninguno"),
            ("freight", "Flete"),
            ("customs", "Aduana"),
            ("insurance", "Seguro"),
            ("transport", "Transporte"),
            ("install", "Instalación"),
            ("logistics", "Logística"),
            ("other", "Otro costo directo"),
        ],
        default="none",
        string="Costo adicional",
    )
    notes = fields.Char(string="Notas")
