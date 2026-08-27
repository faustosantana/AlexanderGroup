# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

REGISTER_MODES = [
    ("invoice_line", "Vincular línea de factura de cliente"),
    ("manual", "Monto manual"),
]


class PurchaseSaleRegisterSaleWizard(models.TransientModel):
    """Registers a real or estimated sale on a purchase.sale.margin.transaction,
    either by linking an existing posted customer invoice line or by typing
    a manual amount. Never creates accounting entries."""

    _name = "purchase.sale.register.sale.wizard"
    _description = "Registrar venta en operación de margen"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación de margen",
        domain="[('company_id', '=', company_id)]",
    )
    new_transaction_name = fields.Char(
        string="Nombre de operación nueva",
        help="Se usa solo si no selecciona una operación existente.",
    )
    mode = fields.Selection(REGISTER_MODES, default="manual", required=True)
    data_origin = fields.Selection(
        [("estimated", "Estimado"), ("manual", "Real (manual)")], default="manual", required=True,
    )
    customer_invoice_line_id = fields.Many2one(
        "account.move.line", string="Línea de factura de cliente",
        domain="[('move_id.move_type', 'in', ('out_invoice', 'out_refund')), "
        "('move_id.state', 'in', ('draft', 'posted')), ('display_type', '=', False)]",
    )
    sale_order_id = fields.Many2one("sale.order", string="Orden de venta")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    product_id = fields.Many2one("product.product", string="Producto")
    description = fields.Char(string="Descripción")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    amount = fields.Monetary(string="Monto", currency_field="currency_id")
    notes = fields.Char(string="Notas")

    @api.onchange("customer_invoice_line_id")
    def _onchange_customer_invoice_line_id(self):
        if self.customer_invoice_line_id:
            self.mode = "invoice_line"
            self.data_origin = "manual"
            self.amount = abs(self.customer_invoice_line_id.price_subtotal)
            self.currency_id = self.customer_invoice_line_id.currency_id
            self.partner_id = self.customer_invoice_line_id.move_id.partner_id
            self.product_id = self.customer_invoice_line_id.product_id
            if self.customer_invoice_line_id.sale_line_ids:
                self.sale_order_id = self.customer_invoice_line_id.sale_line_ids[0].order_id

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
            "customer_id": self.partner_id.id if self.partner_id else False,
        }
        if self.sale_order_id:
            return Transaction.find_or_create_canonical_transaction(
                sale_order=self.sale_order_id, vals=vals
            )
        return Transaction.create(vals)

    def action_confirm(self):
        self.ensure_one()
        if self.mode == "invoice_line" and not self.customer_invoice_line_id:
            raise UserError(_("Seleccione una línea de factura de cliente."))
        if self.mode == "manual" and not self.amount:
            raise UserError(_("Ingrese un monto para el registro manual."))

        transaction = self._get_or_create_transaction()
        Line = self.env["purchase.sale.margin.transaction.line"]

        if self.mode == "invoice_line":
            invoice = self.customer_invoice_line_id.move_id
            transaction.write({"customer_invoice_ids": [(4, invoice.id)]})
            if self.sale_order_id:
                transaction.write({"sale_order_ids": [(4, self.sale_order_id.id)]})
            if not transaction.customer_id and self.partner_id:
                transaction.write({"customer_id": self.partner_id.id})
            Line.create(
                {
                    "transaction_id": transaction.id,
                    "line_type": "sale",
                    "data_origin": "accounting",
                    "sale_order_id": self.sale_order_id.id,
                    "account_move_id": invoice.id,
                    "account_move_line_id": self.customer_invoice_line_id.id,
                    "partner_id": self.partner_id.id,
                    "product_id": self.product_id.id,
                    "currency_id": self.currency_id.id,
                    "description": self.description or self.customer_invoice_line_id.name,
                    "amount_untaxed": abs(self.customer_invoice_line_id.price_subtotal),
                    "amount_total": abs(self.customer_invoice_line_id.price_total),
                    "is_manual": False,
                    "notes": self.notes,
                }
            )
        else:
            if self.sale_order_id:
                transaction.write({"sale_order_ids": [(4, self.sale_order_id.id)]})
            if not transaction.customer_id and self.partner_id:
                transaction.write({"customer_id": self.partner_id.id})
            Line.create(
                {
                    "transaction_id": transaction.id,
                    "line_type": "sale",
                    "data_origin": self.data_origin,
                    "sale_order_id": self.sale_order_id.id,
                    "partner_id": self.partner_id.id,
                    "product_id": self.product_id.id,
                    "currency_id": self.currency_id.id,
                    "description": self.description,
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
