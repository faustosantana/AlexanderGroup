# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COST_USAGE = [
    ("resale_direct", "Reventa directa"),
    ("inventory_pending", "Inventario pendiente de asignación"),
    ("administrative_expense", "Gasto administrativo"),
    ("asset", "Activo"),
    ("internal_service", "Servicio interno"),
    ("mixed", "Compra mixta"),
    ("not_sales_related", "No relacionada con ventas"),
    # 19.0.2.0.0: costos adicionales para líneas de operación de margen.
    ("logistic", "Logística/Distribución"),
    ("financial", "Financiero"),
    ("other", "Otro"),
]

ALLOC_STATUS = [
    ("unallocated", "Sin asignar"),
    ("partial", "Parcial"),
    ("allocated", "Asignada"),
    ("excluded", "Excluida"),
]

LINK_SOURCE = [
    ("sale_line", "Línea de venta"),
    ("purchase_line", "Línea de compra"),
    ("bill_line", "Línea factura proveedor"),
    ("bill_purchase_sale", "Factura→OC→Venta"),
    ("procurement", "Aprovisionamiento"),
    ("origin", "Origin OC"),
    ("origin_single", "Origin OC (única)"),
    ("origin_ambiguous", "Origin OC (ambigua)"),
    ("origin_product_qty", "Origin + producto + cantidad"),
    ("product", "Producto"),
    ("product_qty_company", "Producto + cantidad + compañía"),
    ("ref", "Referencia"),
    ("analytic", "Analítica"),
    ("manual", "Manual"),
    ("rule", "Regla"),
    ("heuristic", "Heurística"),
]


class PurchaseSaleCostLink(models.Model):
    _name = "purchase.sale.cost.link"
    _description = "Enlace costo compra ↔ venta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default=lambda self: _("Nuevo"), tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    sale_id = fields.Many2one("sale.order", string="Orden de venta", index=True, check_company=True)
    sale_line_id = fields.Many2one(
        "sale.order.line", string="Línea de venta", index=True, check_company=True
    )
    purchase_id = fields.Many2one(
        "purchase.order", string="Orden de compra", index=True, check_company=True
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de compra", index=True, check_company=True
    )
    product_id = fields.Many2one("product.product", string="Producto", index=True)
    partner_id = fields.Many2one(related="sale_id.partner_id", store=True)
    supplier_id = fields.Many2one(related="purchase_id.partner_id", store=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda costo",
        default=lambda self: self.env.company.currency_id,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, string="Moneda compañía"
    )
    cost_usage_type = fields.Selection(COST_USAGE, string="Clasificación", default="inventory_pending", tracking=True)
    exclude_from_sales_margin = fields.Boolean(string="Excluir del margen", tracking=True)
    allocation_status = fields.Selection(ALLOC_STATUS, default="unallocated", tracking=True, index=True)
    link_source = fields.Selection(LINK_SOURCE, string="Fuente", default="manual")
    confidence = fields.Integer(string="Confianza %", default=0)
    is_manual = fields.Boolean(string="Manual confirmada", default=False, tracking=True)
    committed_amount = fields.Monetary(
        string="Costo comprometido (OC)", currency_field="currency_id", tracking=True
    )
    realized_amount = fields.Monetary(
        string="Costo realizado (factura)", currency_field="currency_id", tracking=True
    )
    committed_amount_company = fields.Monetary(
        string="Comprometido compañía", currency_field="company_currency_id"
    )
    realized_amount_company = fields.Monetary(
        string="Realizado compañía", currency_field="company_currency_id"
    )
    allocation_ids = fields.One2many("purchase.sale.cost.allocation", "link_id", string="Asignaciones")
    allocation_count = fields.Integer(compute="_compute_allocation_count")
    notes = fields.Text(string="Notas")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("suggested", "Sugerido"),
            ("confirmed", "Confirmado"),
            ("cancelled", "Cancelado"),
        ],
        default="draft",
        tracking=True,
        index=True,
    )

    @api.depends("allocation_ids")
    def _compute_allocation_count(self):
        for rec in self:
            rec.allocation_count = len(rec.allocation_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) in (False, _("Nuevo"), "Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("purchase.sale.cost.link") or _("Link")
        return super().create(vals_list)

    @api.constrains("sale_id", "purchase_id", "company_id")
    def _check_same_company(self):
        for rec in self:
            for doc in (rec.sale_id, rec.purchase_id):
                if doc and doc.company_id and rec.company_id and doc.company_id != rec.company_id:
                    raise ValidationError(_("No se permiten enlaces entre compañías distintas."))

    def action_confirm(self):
        for rec in self:
            rec.write({"state": "confirmed", "is_manual": True if rec.is_manual or rec.link_source == "manual" else rec.is_manual})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_open_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignaciones"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": [("link_id", "=", self.id)],
            "context": {"default_link_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_recalculate(self):
        Trace = self.env["purchase.sale.trace.engine"]
        for rec in self:
            if rec.is_manual and rec.state == "confirmed":
                continue
            Trace.recompute_link(rec)
        return True
