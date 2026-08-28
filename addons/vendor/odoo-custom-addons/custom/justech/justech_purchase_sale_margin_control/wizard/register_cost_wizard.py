# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.cost_link import COST_USAGE

REGISTER_MODES = [
    ("bill_line", "Vincular línea de factura de proveedor"),
    ("manual", "Monto manual"),
]


class PurchaseSaleRegisterCostWizard(models.TransientModel):
    """Registers a real or estimated cost on a purchase.sale.margin.transaction,
    either by linking an existing posted vendor bill line or by typing a
    manual amount. Never creates accounting entries."""

    _name = "purchase.sale.register.cost.wizard"
    _description = "Registrar costo en operación de margen"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación de margen",
        domain="[('company_id', '=', company_id), ('is_merged', '=', False)]",
    )
    new_transaction_name = fields.Char(
        string="Nombre de operación nueva",
        help="Se usa solo si no selecciona una operación existente.",
    )
    mode = fields.Selection(REGISTER_MODES, default="manual", required=True)
    data_origin = fields.Selection(
        [("estimated", "Estimado"), ("manual", "Real (manual)")], default="manual", required=True,
    )
    vendor_bill_line_id = fields.Many2one(
        "account.move.line", string="Línea de factura de proveedor",
        domain="[('move_id.move_type', 'in', ('in_invoice', 'in_refund')), "
        "('move_id.state', 'in', ('draft', 'posted')), ('display_type', '=', False)]",
    )
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    partner_id = fields.Many2one("res.partner", string="Proveedor")
    product_id = fields.Many2one("product.product", string="Producto")
    description = fields.Char(string="Descripción")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    amount = fields.Monetary(string="Monto", currency_field="currency_id")
    cost_usage_type = fields.Selection(COST_USAGE, default="resale_direct", string="Clasificación")
    notes = fields.Char(string="Notas")

    @api.onchange("vendor_bill_line_id")
    def _onchange_vendor_bill_line_id(self):
        if self.vendor_bill_line_id:
            self.mode = "bill_line"
            self.data_origin = "manual"
            self.amount = abs(self.vendor_bill_line_id.price_subtotal)
            self.currency_id = self.vendor_bill_line_id.currency_id
            self.partner_id = self.vendor_bill_line_id.move_id.partner_id
            self.product_id = self.vendor_bill_line_id.product_id
            if self.vendor_bill_line_id.purchase_line_id:
                self.purchase_order_id = self.vendor_bill_line_id.purchase_line_id.order_id
                self.cost_usage_type = self.vendor_bill_line_id.purchase_line_id.cost_usage_type or self.cost_usage_type

    def _get_or_create_transaction(self):
        if self.transaction_id:
            return self.transaction_id
        Transaction = self.env["purchase.sale.margin.transaction"]
        vals = {
            "company_id": self.company_id.id,
            "name": self.new_transaction_name or self.description or _("Operación manual"),
            "transaction_type": "manual",
            "source": "manual",
            "state": "draft",
            "customer_id": False,
            "supplier_ids": [(6, 0, [self.partner_id.id])] if self.partner_id else False,
        }
        so = self.env["sale.order"]
        if self.purchase_order_id:
            existing = Transaction.search(
                Transaction._operational_domain()
                + [("purchase_order_ids", "in", self.purchase_order_id.id)],
                limit=1,
            )
            if existing:
                return existing
            so = self.purchase_order_id.order_line.mapped("sale_line_id.order_id")[:1]
            vals["purchase_order_ids"] = [(4, self.purchase_order_id.id)]
        if so:
            return Transaction.find_or_create_canonical_transaction(sale_order=so, vals=vals)
        return Transaction.create(vals)

    def action_confirm(self):
        self.ensure_one()
        if self.mode == "bill_line" and not self.vendor_bill_line_id:
            raise UserError(_("Seleccione una línea de factura de proveedor."))
        if self.mode == "manual" and not self.amount:
            raise UserError(_("Ingrese un monto para el registro manual."))

        transaction = self._get_or_create_transaction()
        Line = self.env["purchase.sale.margin.transaction.line"]

        if self.mode == "bill_line":
            bill = self.vendor_bill_line_id.move_id
            transaction.write({"vendor_bill_ids": [(4, bill.id)]})
            if self.purchase_order_id:
                transaction.write({"purchase_order_ids": [(4, self.purchase_order_id.id)]})
            Line.create(
                {
                    "transaction_id": transaction.id,
                    "line_type": "cost",
                    "data_origin": "accounting",
                    "purchase_order_id": self.purchase_order_id.id,
                    "account_move_id": bill.id,
                    "account_move_line_id": self.vendor_bill_line_id.id,
                    "partner_id": self.partner_id.id,
                    "product_id": self.product_id.id,
                    "currency_id": self.currency_id.id,
                    "description": self.description or self.vendor_bill_line_id.name,
                    "cost_usage_type": self.cost_usage_type,
                    "amount_untaxed": abs(self.vendor_bill_line_id.price_subtotal),
                    "amount_total": abs(self.vendor_bill_line_id.price_total),
                    "is_manual": False,
                    "notes": self.notes,
                }
            )
        else:
            if self.purchase_order_id:
                transaction.write({"purchase_order_ids": [(4, self.purchase_order_id.id)]})
            Line.create(
                {
                    "transaction_id": transaction.id,
                    "line_type": "cost",
                    "data_origin": self.data_origin,
                    "purchase_order_id": self.purchase_order_id.id,
                    "partner_id": self.partner_id.id,
                    "product_id": self.product_id.id,
                    "currency_id": self.currency_id.id,
                    "description": self.description,
                    "cost_usage_type": self.cost_usage_type,
                    "amount_untaxed": self.amount,
                    "amount_total": self.amount,
                    "is_manual": True,
                    "notes": self.notes,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Operación de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "form",
            "res_id": transaction.id,
        }
