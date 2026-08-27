# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

from .cost_link import COST_USAGE, LINK_SOURCE

ALLOC_STATES = [
    ("draft", "Borrador"),
    ("suggested", "Sugerida"),
    ("confirmed", "Confirmada"),
    ("partial", "Parcial"),
    ("complete", "Completa"),
    ("excluded", "Excluida"),
    ("conflict", "Conflicto"),
    ("cancelled", "Cancelada"),
]

ALLOC_METHODS = [
    ("line", "Línea"),
    ("qty", "Cantidad"),
    ("amount", "Monto"),
    ("percent", "Porcentaje"),
    ("weight", "Peso"),
    ("volume", "Volumen"),
    ("manual", "Manual"),
]


class PurchaseSaleCostAllocation(models.Model):
    _name = "purchase.sale.cost.allocation"
    _description = "Asignación de costo a venta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default=lambda self: _("Nueva"), tracking=True)
    link_id = fields.Many2one("purchase.sale.cost.link", string="Enlace", ondelete="cascade", index=True)
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación de margen",
        index=True, ondelete="set null", check_company=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    vendor_bill_id = fields.Many2one("account.move", string="Factura proveedor", index=True, check_company=True)
    vendor_bill_line_id = fields.Many2one(
        "account.move.line", string="Línea factura proveedor", index=True, check_company=True
    )
    purchase_order_id = fields.Many2one("purchase.order", string="OC", index=True, check_company=True)
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line", string="Línea OC", index=True, check_company=True
    )
    sale_order_id = fields.Many2one("sale.order", string="Orden venta", index=True, check_company=True)
    sale_order_line_id = fields.Many2one(
        "sale.order.line", string="Línea venta", index=True, check_company=True
    )
    customer_invoice_id = fields.Many2one(
        "account.move", string="Factura cliente", index=True, check_company=True
    )
    customer_invoice_line_id = fields.Many2one(
        "account.move.line", string="Línea factura cliente", index=True, check_company=True
    )
    partner_id = fields.Many2one("res.partner", string="Cliente", index=True)
    supplier_id = fields.Many2one("res.partner", string="Proveedor", index=True)
    product_id = fields.Many2one("product.product", string="Producto", index=True)
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, string="Moneda compañía"
    )
    source_amount = fields.Monetary(string="Monto origen", currency_field="currency_id")
    allocated_amount = fields.Monetary(string="Monto asignado", currency_field="currency_id", tracking=True)
    allocated_amount_company_currency = fields.Monetary(
        string="Monto compañía", currency_field="company_currency_id"
    )
    allocation_percentage = fields.Float(string="% asignado")
    allocated_quantity = fields.Float(string="Cantidad asignada")
    allocation_method = fields.Selection(ALLOC_METHODS, default="manual", string="Método")
    cost_usage_type = fields.Selection(COST_USAGE, string="Clasificación")
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
    source = fields.Selection(LINK_SOURCE, default="manual", string="Fuente")
    confidence = fields.Integer(string="Confianza %", default=0)
    state = fields.Selection(ALLOC_STATES, default="draft", tracking=True, index=True)
    is_manual = fields.Boolean(default=False, tracking=True)
    confirmed_by_id = fields.Many2one("res.users", string="Confirmado por", readonly=True)
    confirmed_at = fields.Datetime(string="Confirmado el", readonly=True)
    fx_rate = fields.Float(string="Tasa aplicada", digits=(16, 6))
    fx_rate_date = fields.Date(string="Fecha tasa")
    fx_alert = fields.Boolean(string="Alerta FX", default=False)
    notes = fields.Text(string="Notas")
    exclude_from_sales_margin = fields.Boolean(string="Excluir del margen")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nueva")) in (False, _("Nueva"), "Nueva"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("purchase.sale.cost.allocation") or _("ALLOC")
                )
        records = super().create(vals_list)
        records._recompute_company_amount()
        records._sync_transaction_line()
        return records

    def write(self, vals):
        for rec in self:
            if rec.is_manual and rec.state == "confirmed":
                forbidden = {"allocated_amount", "sale_order_id", "sale_order_line_id", "vendor_bill_line_id"}
                if forbidden.intersection(vals) and not self.env.context.get("force_manual_override"):
                    if not self.env.user.has_group(
                        "justech_purchase_sale_margin_control.group_margin_finance"
                    ):
                        raise UserError(
                            _("No se puede sobrescribir una asignación manual confirmada.")
                        )
        res = super().write(vals)
        if self.env.context.get("skip_fx_recompute"):
            return res
        if any(
            k in vals
            for k in ("allocated_amount", "currency_id", "company_id", "fx_rate_date")
        ):
            self._recompute_company_amount()
        if any(
            k in vals
            for k in (
                "transaction_id", "allocated_amount", "allocated_amount_company_currency",
                "cost_usage_type", "state", "sale_order_id",
            )
        ):
            self._sync_transaction_line()
        return res

    def _sync_transaction_line(self):
        """Mirror confirmed allocations linked to a margin transaction into a
        purchase.sale.margin.transaction.line so the transaction's computed
        amounts ("Compute amounts from linked allocations + manual lines")
        stay consistent with a single aggregation source."""
        Line = self.env["purchase.sale.margin.transaction.line"]
        for rec in self:
            if not rec.transaction_id:
                continue
            existing = Line.search(
                [("transaction_id", "=", rec.transaction_id.id), ("account_move_line_id", "=", rec.vendor_bill_line_id.id)],
                limit=1,
            ) if rec.vendor_bill_line_id else Line
            vals = {
                "transaction_id": rec.transaction_id.id,
                "line_type": "cost",
                "data_origin": "manual" if rec.is_manual else "accounting",
                "purchase_order_id": rec.purchase_order_id.id,
                "account_move_id": rec.vendor_bill_id.id,
                "account_move_line_id": rec.vendor_bill_line_id.id,
                "partner_id": rec.supplier_id.id,
                "product_id": rec.product_id.id,
                "currency_id": rec.currency_id.id,
                "cost_usage_type": rec.cost_usage_type,
                "amount_untaxed": rec.allocated_amount,
                "amount_total": rec.allocated_amount,
                "is_manual": rec.is_manual,
                "state": "excluded" if rec.state in ("cancelled", "excluded") else "confirmed",
                "exclude_from_margin": rec.exclude_from_sales_margin,
            }
            if existing:
                existing.with_context(skip_line_sync=True).write(vals)
            else:
                Line.create(vals)

    def _recompute_company_amount(self):
        for rec in self:
            company_cur = rec.company_currency_id
            amount = rec.allocated_amount or 0.0
            rate = rec.fx_rate or 0.0
            fx_alert = False
            if rec.currency_id and company_cur and rec.currency_id != company_cur:
                date = rec.fx_rate_date or fields.Date.context_today(rec)
                try:
                    converted = rec.currency_id._convert(
                        amount, company_cur, rec.company_id, date
                    )
                    if amount:
                        rate = abs(converted / amount) if amount else rate
                    amount_co = converted
                except Exception:  # noqa: BLE001
                    amount_co = amount
                    fx_alert = True
            else:
                amount_co = amount
            rec.with_context(force_manual_override=True, skip_fx_recompute=True).write(
                {
                    "allocated_amount_company_currency": amount_co,
                    "fx_rate": rate,
                    "fx_alert": fx_alert,
                }
            )

    @api.constrains("company_id", "sale_order_id", "purchase_order_id", "vendor_bill_id", "customer_invoice_id")
    def _check_company_coherence(self):
        for rec in self:
            docs = [
                rec.sale_order_id,
                rec.purchase_order_id,
                rec.vendor_bill_id,
                rec.customer_invoice_id,
            ]
            for doc in docs:
                if doc and doc.company_id and rec.company_id and doc.company_id != rec.company_id:
                    raise ValidationError(_("Asignación multiempresa prohibida."))

    @api.constrains("allocated_amount", "vendor_bill_line_id", "purchase_order_line_id", "state")
    def _check_over_allocation(self):
        for rec in self:
            if rec.state in ("cancelled", "excluded"):
                continue
            if float_is_zero(rec.allocated_amount, precision_digits=2):
                continue
            # Allow negative only for refunds
            if rec.allocated_amount < 0:
                move = rec.vendor_bill_id
                if not move or move.move_type not in ("in_refund", "out_refund"):
                    raise ValidationError(
                        _("Montos negativos solo permitidos en notas de crédito.")
                    )
            available = rec._available_source_amount()
            if available is None:
                continue
            allocated_others = sum(
                rec.search(
                    [
                        ("id", "!=", rec.id),
                        ("state", "not in", ("cancelled", "excluded")),
                        ("vendor_bill_line_id", "=", rec.vendor_bill_line_id.id),
                    ]
                ).mapped("allocated_amount")
            ) if rec.vendor_bill_line_id else 0.0
            total = allocated_others + rec.allocated_amount
            if float_compare(abs(total), abs(available) + 0.01, precision_digits=2) > 0:
                raise ValidationError(
                    _("Sobreasignación: disponible %(avail)s, intentado %(total)s.")
                    % {"avail": available, "total": total}
                )

    def _available_source_amount(self):
        self.ensure_one()
        if self.vendor_bill_line_id:
            return abs(self.vendor_bill_line_id.price_subtotal)
        if self.purchase_order_line_id:
            return abs(self.purchase_order_line_id.price_subtotal)
        return None

    def action_confirm(self):
        for rec in self:
            if rec.vendor_bill_id and rec.vendor_bill_id.state == "cancel":
                raise UserError(_("No se puede confirmar sobre factura cancelada."))
            if rec.customer_invoice_id and rec.customer_invoice_id.state == "cancel":
                raise UserError(_("No se puede confirmar sobre factura cliente cancelada."))
            rec.write(
                {
                    "state": "confirmed",
                    "is_manual": True if rec.source == "manual" else rec.is_manual,
                    "confirmed_by_id": self.env.user.id,
                    "confirmed_at": fields.Datetime.now(),
                }
            )
        return True

    def action_exclude(self):
        self.write({"state": "excluded", "exclude_from_sales_margin": True})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True
