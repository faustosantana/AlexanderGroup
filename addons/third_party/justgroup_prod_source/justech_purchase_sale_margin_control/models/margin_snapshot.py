# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

SNAPSHOT_STATES = [
    ("draft", "Borrador"),
    ("final", "Final"),
]


class PurchaseSaleMarginSnapshot(models.Model):
    _name = "purchase.sale.margin.snapshot"
    _description = "Foto de margen estimado/real por orden de venta"
    _inherit = ["mail.thread"]
    _order = "snapshot_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default=lambda self: _("Nuevo"))
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    sale_id = fields.Many2one(
        "sale.order", string="Orden de venta", required=True, index=True, check_company=True, ondelete="cascade"
    )
    partner_id = fields.Many2one(related="sale_id.partner_id", store=True, string="Cliente")
    currency_id = fields.Many2one(related="sale_id.currency_id", store=True)
    snapshot_date = fields.Datetime(default=fields.Datetime.now, required=True)
    state = fields.Selection(SNAPSHOT_STATES, default="draft", tracking=True)

    revenue_amount = fields.Monetary(string="Ingreso (sin ITBIS)", currency_field="currency_id")
    estimated_cost_amount = fields.Monetary(string="Costo estimado", currency_field="currency_id")
    real_cost_amount = fields.Monetary(string="Costo real", currency_field="currency_id")
    unallocated_cost_amount = fields.Monetary(
        string="Costo comprometido sin asignar", currency_field="currency_id"
    )

    estimated_margin = fields.Monetary(
        string="Margen estimado", currency_field="currency_id", compute="_compute_margins", store=True
    )
    estimated_margin_pct = fields.Float(
        string="Margen estimado %", compute="_compute_margins", store=True
    )
    real_margin = fields.Monetary(
        string="Margen real", currency_field="currency_id", compute="_compute_margins", store=True
    )
    real_margin_pct = fields.Float(string="Margen real %", compute="_compute_margins", store=True)
    margin_variance = fields.Monetary(
        string="Variación (real-estimado)", currency_field="currency_id", compute="_compute_margins", store=True
    )

    notes = fields.Text(string="Notas")

    @api.depends("revenue_amount", "estimated_cost_amount", "real_cost_amount")
    def _compute_margins(self):
        for rec in self:
            rec.estimated_margin = rec.revenue_amount - rec.estimated_cost_amount
            rec.real_margin = rec.revenue_amount - rec.real_cost_amount
            rec.margin_variance = rec.real_margin - rec.estimated_margin
            rec.estimated_margin_pct = (
                (rec.estimated_margin / rec.revenue_amount * 100.0) if rec.revenue_amount else 0.0
            )
            rec.real_margin_pct = (
                (rec.real_margin / rec.revenue_amount * 100.0) if rec.revenue_amount else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) in (False, _("Nuevo"), "Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "purchase.sale.margin.snapshot"
                ) or _("SNAP")
        return super().create(vals_list)

    def action_recompute(self):
        MarginService = self.env["purchase.sale.margin.service"]
        for rec in self:
            data = MarginService.compute_for_sale_order(rec.sale_id)
            rec.write(
                {
                    "revenue_amount": data["revenue"],
                    "estimated_cost_amount": data["estimated_cost"],
                    "real_cost_amount": data["real_cost"],
                    "unallocated_cost_amount": data["unallocated_cost"],
                    "snapshot_date": fields.Datetime.now(),
                }
            )
        return True

    def action_set_final(self):
        self.write({"state": "final"})
        return True
