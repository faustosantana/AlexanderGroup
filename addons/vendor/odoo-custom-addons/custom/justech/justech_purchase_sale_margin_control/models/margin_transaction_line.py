# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero

from .cost_link import COST_USAGE

LINE_TYPES = [
    ("sale", "Venta"),
    ("cost", "Costo"),
]

DATA_ORIGINS = [
    ("accounting", "Contable"),
    ("manual", "Manual"),
    ("estimated", "Estimado"),
]

LINE_STATES = [
    ("draft", "Borrador"),
    ("confirmed", "Confirmada"),
    ("excluded", "Excluida"),
]

COST_SOURCE = [
    ("direct_purchase", "Compra directa"),
    ("inventory", "Inventario"),
    ("manual", "Manual"),
    ("additional_cost", "Costo adicional"),
    ("service", "Servicio"),
]


class PurchaseSaleMarginTransactionLine(models.Model):
    """A single fact (sale or cost) attached to a purchase.sale.margin.transaction.
    data_origin distinguishes an 'estimated' commitment (SO/PO) from the
    'accounting'/'manual' real figure (posted invoice/bill or manual entry);
    this is the single source of truth the parent transaction aggregates
    from (see PurchaseSaleMarginTransaction._compute_amounts)."""

    _name = "purchase.sale.margin.transaction.line"
    _description = "Línea de operación de margen (venta o costo)"
    _order = "transaction_id, line_type, id"
    _check_company_auto = True

    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación", required=True,
        ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(
        related="transaction_id.company_id", store=True, string="Compañía", index=True,
    )
    line_type = fields.Selection(LINE_TYPES, string="Tipo de línea", required=True, default="cost")
    data_origin = fields.Selection(DATA_ORIGINS, string="Origen del dato", required=True, default="manual")
    state = fields.Selection(LINE_STATES, string="Estado", default="confirmed")

    partner_id = fields.Many2one("res.partner", string="Contacto")
    product_id = fields.Many2one("product.product", string="Producto")
    description = fields.Char(string="Descripción")

    sale_order_id = fields.Many2one("sale.order", string="Orden de venta", check_company=True, index=True)
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta",
        check_company=True,
        index=True,
        help="Línea de venta cubierta por costo manual / inventario histórico (solo márgenes).",
    )
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", check_company=True, index=True)
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de orden de compra", check_company=True, index=True,
        help="19.0.3.0.0: referencia a la línea de OC de origen cuando la línea de costo "
        "estimado se creó/asignó vía el asistente de múltiples órdenes de compra.",
    )
    account_move_id = fields.Many2one("account.move", string="Factura/Documento", check_company=True, index=True)
    account_move_line_id = fields.Many2one("account.move.line", string="Línea de factura", check_company=True)

    currency_id = fields.Many2one(
        "res.currency", string="Moneda",
        default=lambda self: self.env.company.currency_id,
    )
    amount_untaxed = fields.Monetary(string="Base imponible", currency_field="currency_id")
    amount_tax = fields.Monetary(string="Impuesto", currency_field="currency_id")
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    amount_company_currency = fields.Monetary(
        string="Monto (moneda compañía)", compute="_compute_amount_company_currency", store=True,
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        related="transaction_id.company_currency_id", store=True, string="Moneda compañía",
    )

    cost_usage_type = fields.Selection(COST_USAGE, string="Clasificación de costo")
    cost_source = fields.Selection(
        COST_SOURCE,
        string="Origen del costo",
        default="direct_purchase",
        help="Clasificación técnica de procedencia del costo para auditoría: "
        "compra directa, inventario (SVL/salida), manual, adicional o servicio.",
        index=True,
    )
    stock_move_id = fields.Many2one(
        "stock.move",
        string="Movimiento de stock",
        ondelete="set null",
        index=True,
        help="Movimiento de salida/devolución cuando el costo proviene de inventario.",
    )
    is_manual = fields.Boolean(string="Manual", default=True)
    notes = fields.Text(string="Notas")
    exclude_from_margin = fields.Boolean(string="Excluir del margen", default=False)
    quantity = fields.Float(
        string="Cantidad",
        help="19.0.3.0.0: cantidad asociada a la línea (p.ej. cantidad de la línea de OC "
        "asignada a esta operación vía el asistente de múltiples órdenes de compra).",
    )

    @api.depends(
        "amount_untaxed",
        "currency_id",
        "line_type",
        "transaction_id.company_id",
        "transaction_id.transaction_date",
        "account_move_id",
        "account_move_id.state",
        "account_move_id.move_type",
        "account_move_id.amount_untaxed_signed",
    )
    def _compute_amount_company_currency(self):
        for rec in self:
            company = rec.transaction_id.company_id or rec.env.company
            company_currency = company.currency_id
            move = rec.account_move_id
            # Prefer the line's own untaxed amount (supports partial vendor-bill shares
            # per POL). Only fall back to the full move when the line has no amount.
            base = rec.amount_untaxed or 0.0
            if (
                float_is_zero(base, precision_digits=2)
                and move
                and move.state == "posted"
                and "amount_untaxed_signed" in move._fields
            ):
                base = abs(move.amount_untaxed_signed or 0.0)
                refund_types = ("in_refund",) if rec.line_type == "cost" else ("out_refund",)
                if move.move_type in refund_types:
                    base = -base
            if not rec.currency_id or rec.currency_id == company_currency:
                rec.amount_company_currency = base
                continue
            date = rec.transaction_id.transaction_date or fields.Date.context_today(rec)
            # When base came from a refund move with negative sign already applied,
            # convert the absolute and re-apply sign if needed.
            rec.amount_company_currency = rec.currency_id._convert(
                base, company_currency, company, date
            )

    @api.onchange("line_type")
    def _onchange_line_type(self):
        if self.line_type == "sale":
            self.cost_usage_type = False

    @api.constrains("transaction_id", "sale_order_id", "purchase_order_id", "account_move_id", "purchase_order_line_id")
    def _check_same_company(self):
        for rec in self:
            company = rec.transaction_id.company_id
            if not company:
                continue
            for doc in (rec.sale_order_id, rec.sale_order_line_id, rec.purchase_order_id, rec.account_move_id, rec.purchase_order_line_id):
                if doc and doc.company_id and doc.company_id != company:
                    raise ValidationError(_("La línea referencia un documento de otra compañía."))
