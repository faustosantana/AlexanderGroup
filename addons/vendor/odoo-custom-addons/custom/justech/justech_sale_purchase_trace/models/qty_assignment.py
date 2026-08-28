# -*- coding: utf-8 -*-
"""Asignación de cantidad compra/factura→venta (comercial, sin alterar asientos)."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class JustechPurchaseSaleQtyAssignment(models.Model):
    _name = "justech.purchase.sale.qty.assignment"
    _description = "Asignación cantidad compra→venta"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(default=lambda self: _("Asignación"), required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Línea OC",
        required=False,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    purchase_order_id = fields.Many2one(
        related="purchase_line_id.order_id",
        store=True,
        index=True,
        string="OC",
    )
    vendor_bill_line_id = fields.Many2one(
        "account.move.line",
        string="Línea factura proveedor",
        required=False,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    vendor_bill_id = fields.Many2one(
        related="vendor_bill_line_id.move_id",
        store=True,
        index=True,
        string="Factura proveedor",
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea venta",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    sale_order_id = fields.Many2one(
        related="sale_line_id.order_id",
        store=True,
        index=True,
        string="Orden de venta",
    )
    product_id = fields.Many2one(
        "product.product",
        compute="_compute_product_id",
        store=True,
        index=True,
    )
    quantity = fields.Float(string="Cantidad asignada", required=True)
    amount = fields.Monetary(
        string="Monto asignado",
        currency_field="currency_id",
        help="Monto comercial asignado (no modifica el asiento).",
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
    )
    state = fields.Selection(
        [
            ("active", "Activa"),
            ("cancelled", "Cancelada"),
        ],
        default="active",
        required=True,
        index=True,
    )
    note = fields.Char(string="Nota")

    @api.depends("purchase_line_id.product_id", "vendor_bill_line_id.product_id")
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = (
                rec.purchase_line_id.product_id
                or rec.vendor_bill_line_id.product_id
            )

    @api.depends(
        "purchase_line_id.currency_id",
        "vendor_bill_line_id.currency_id",
        "company_id.currency_id",
    )
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = (
                rec.purchase_line_id.currency_id
                or rec.vendor_bill_line_id.currency_id
                or rec.company_id.currency_id
            )

    @api.constrains(
        "quantity",
        "amount",
        "purchase_line_id",
        "vendor_bill_line_id",
        "state",
    )
    def _check_quantity(self):
        for rec in self:
            if rec.state != "active":
                continue
            if not rec.purchase_line_id and not rec.vendor_bill_line_id:
                raise ValidationError(
                    _(
                        "La asignación debe referenciar una línea de OC "
                        "o una línea de factura proveedor."
                    )
                )
            if float_compare(rec.quantity, 0.0, precision_digits=4) <= 0:
                raise ValidationError(_("La cantidad asignada debe ser positiva."))
            if rec.purchase_line_id:
                # Dedupe bare sale_line_id M2O with ASG for the same SOL.
                pol = rec.purchase_line_id.with_context(
                    justech_skip_m2o_for_sale_line_id=rec.sale_line_id.id
                    if rec.sale_line_id
                    else False
                )
                available = pol._justech_qty_available_to_assign(
                    exclude_assignment_ids=rec.ids
                )
                if float_compare(rec.quantity, available, precision_digits=4) > 0:
                    raise ValidationError(
                        _(
                            "No se puede asignar %(qty)s: disponible %(avail)s "
                            "en la línea de OC."
                        )
                        % {"qty": rec.quantity, "avail": available}
                    )
                if rec.sale_line_id.company_id != rec.purchase_line_id.company_id:
                    raise ValidationError(
                        _("No se puede asignar una OC de otra compañía a la venta.")
                    )
            if rec.vendor_bill_line_id:
                aml = rec.vendor_bill_line_id
                move = aml.move_id
                if move.move_type not in ("in_invoice", "in_refund"):
                    raise ValidationError(
                        _("Solo se permiten facturas o notas de crédito de proveedor.")
                    )
                if move.state == "cancel":
                    raise ValidationError(
                        _("No se puede relacionar una factura proveedor cancelada.")
                    )
                if aml.company_id != rec.sale_line_id.company_id:
                    raise ValidationError(
                        _(
                            "No se puede relacionar una factura proveedor "
                            "de otra compañía."
                        )
                    )
                if not rec.purchase_line_id:
                    avail_qty = aml._justech_bill_qty_available(
                        exclude_assignment_ids=rec.ids
                    )
                    if float_compare(rec.quantity, avail_qty, precision_digits=4) > 0:
                        raise ValidationError(
                            _(
                                "No se puede asignar %(qty)s: disponible %(avail)s "
                                "en la línea de factura proveedor."
                            )
                            % {"qty": rec.quantity, "avail": avail_qty}
                        )
                    avail_amt = aml._justech_bill_amount_available(
                        exclude_assignment_ids=rec.ids
                    )
                    if float_compare(rec.amount or 0.0, 0.0, precision_digits=4) > 0 and (
                        float_compare(rec.amount, avail_amt, precision_digits=4) > 0
                    ):
                        raise ValidationError(
                            _(
                                "No se puede asignar el monto %(amt)s: disponible %(avail)s "
                                "en la línea de factura proveedor."
                            )
                            % {"amt": rec.amount, "avail": avail_amt}
                        )
            product = rec.product_id
            if (
                product
                and rec.sale_line_id.product_id
                and product != rec.sale_line_id.product_id
            ):
                raise ValidationError(
                    _("El producto de la compra no coincide con la venta.")
                )

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True
