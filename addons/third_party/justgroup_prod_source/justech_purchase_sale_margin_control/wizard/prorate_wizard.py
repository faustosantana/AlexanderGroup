# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

PRORATE_METHODS = [
    ("qty", "Cantidad"),
    ("amount", "Monto de compra"),
    ("weight", "Peso"),
    ("volume", "Volumen"),
]

ADDITIONAL_COST_TYPES = [
    ("freight", "Flete"),
    ("customs", "Aduana"),
    ("insurance", "Seguro"),
    ("transport", "Transporte"),
    ("install", "Instalación"),
    ("logistics", "Logística"),
    ("other", "Otro costo directo"),
]


class PurchaseSaleProrateWizard(models.TransientModel):
    _name = "purchase.sale.prorate.wizard"
    _description = "Prorratear costo adicional entre líneas de compra/venta"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    vendor_bill_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de costo adicional",
        domain="[('move_id.move_type', 'in', ('in_invoice', 'in_refund')), "
        "('display_type', '=', False)]",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Orden de compra a prorratear"
    )
    additional_cost_type = fields.Selection(
        ADDITIONAL_COST_TYPES, default="freight", required=True, string="Tipo de costo"
    )
    prorate_method = fields.Selection(PRORATE_METHODS, default="amount", required=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    total_amount = fields.Monetary(
        string="Monto a prorratear", currency_field="currency_id", required=True
    )
    line_ids = fields.One2many(
        "purchase.sale.prorate.wizard.line", "wizard_id", string="Líneas objetivo"
    )
    total_base = fields.Float(compute="_compute_totals")
    total_share_pct = fields.Float(compute="_compute_totals")

    @api.onchange("vendor_bill_line_id")
    def _onchange_vendor_bill_line_id(self):
        if self.vendor_bill_line_id:
            self.total_amount = abs(self.vendor_bill_line_id.price_subtotal)
            self.currency_id = self.vendor_bill_line_id.currency_id
            if self.vendor_bill_line_id.purchase_line_id:
                self.purchase_order_id = self.vendor_bill_line_id.purchase_line_id.order_id

    @api.depends("line_ids.base_value")
    def _compute_totals(self):
        for rec in self:
            rec.total_base = sum(rec.line_ids.mapped("base_value"))
            rec.total_share_pct = sum(rec.line_ids.mapped("share_pct"))

    def action_load_lines(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_("Seleccione una orden de compra para cargar sus líneas."))
        Line = self.env["purchase.sale.prorate.wizard.line"]
        self.line_ids.unlink()
        vals_list = []
        for po_line in self.purchase_order_id.order_line.filtered(lambda l: not l.display_type):
            link = po_line.cost_link_ids[:1]
            base_value = {
                "qty": po_line.product_qty,
                "amount": po_line.price_subtotal,
                "weight": po_line.product_id.weight * po_line.product_qty,
                "volume": po_line.product_id.volume * po_line.product_qty,
            }.get(self.prorate_method, po_line.price_subtotal)
            vals_list.append(
                {
                    "wizard_id": self.id,
                    "purchase_order_line_id": po_line.id,
                    "sale_order_id": link.sale_id.id if link else False,
                    "sale_order_line_id": link.sale_line_id.id if link else False,
                    "base_value": base_value,
                }
            )
        Line.create(vals_list)
        self._recompute_shares()
        return True

    def _recompute_shares(self):
        self.ensure_one()
        total_base = sum(self.line_ids.mapped("base_value"))
        for line in self.line_ids:
            share_pct = (line.base_value / total_base * 100.0) if total_base else 0.0
            proposed = self.total_amount * share_pct / 100.0
            line.write({"share_pct": share_pct, "proposed_amount": proposed})

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No hay líneas cargadas para prorratear."))
        self._recompute_shares()
        if float_is_zero(sum(self.line_ids.mapped("base_value")), precision_digits=2):
            raise UserError(_("La base de prorrateo seleccionada es cero para todas las líneas."))

        Allocation = self.env["purchase.sale.cost.allocation"]
        Trace = self.env["purchase.sale.trace.engine"]
        created = Allocation
        for line in self.line_ids:
            if float_is_zero(line.proposed_amount, precision_digits=2):
                continue
            link = False
            if line.purchase_order_line_id:
                link = Trace.get_or_create_link_for_purchase_line(line.purchase_order_line_id)
            sale_order_id = line.sale_order_id.id or (link.sale_id.id if link else False)
            sale_order_line_id = line.sale_order_line_id.id or (
                link.sale_line_id.id if link else False
            )
            vals = {
                "link_id": link.id if link else False,
                "company_id": self.company_id.id,
                "vendor_bill_id": self.vendor_bill_line_id.move_id.id
                if self.vendor_bill_line_id
                else False,
                "vendor_bill_line_id": self.vendor_bill_line_id.id
                if self.vendor_bill_line_id
                else False,
                "purchase_order_id": line.purchase_order_line_id.order_id.id
                if line.purchase_order_line_id
                else False,
                "purchase_order_line_id": line.purchase_order_line_id.id
                if line.purchase_order_line_id
                else False,
                "sale_order_id": sale_order_id,
                "sale_order_line_id": sale_order_line_id,
                "supplier_id": self.vendor_bill_line_id.move_id.partner_id.id
                if self.vendor_bill_line_id
                else False,
                "product_id": line.purchase_order_line_id.product_id.id
                if line.purchase_order_line_id
                else False,
                "currency_id": self.currency_id.id,
                "source_amount": self.total_amount,
                "allocated_amount": line.proposed_amount,
                "allocation_method": self.prorate_method,
                "additional_cost_type": self.additional_cost_type,
                "cost_usage_type": "resale_direct" if sale_order_id else "inventory_pending",
                "source": "rule",
                "confidence": 80 if sale_order_id else 30,
                "is_manual": True,
                "state": "confirmed" if sale_order_id else "draft",
                "confirmed_by_id": self.env.user.id if sale_order_id else False,
                "confirmed_at": fields.Datetime.now() if sale_order_id else False,
            }
            created |= Allocation.create(vals)

        return {
            "type": "ir.actions.act_window",
            "name": _("Prorrateo aplicado"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }


class PurchaseSaleProrateWizardLine(models.TransientModel):
    _name = "purchase.sale.prorate.wizard.line"
    _description = "Línea objetivo del asistente de prorrateo"

    wizard_id = fields.Many2one("purchase.sale.prorate.wizard", required=True, ondelete="cascade")
    purchase_order_line_id = fields.Many2one("purchase.order.line", string="Línea de compra")
    sale_order_id = fields.Many2one("sale.order", string="Orden de venta")
    sale_order_line_id = fields.Many2one("sale.order.line", string="Línea de venta")
    base_value = fields.Float(string="Base de prorrateo")
    share_pct = fields.Float(string="% asignado", readonly=True)
    proposed_amount = fields.Monetary(
        string="Monto propuesto", currency_field="currency_id", readonly=True
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")
