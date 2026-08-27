# -*- coding: utf-8 -*-
"""Helpers comerciales sobre líneas de factura proveedor (sin tocar asientos)."""
from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    justech_bill_qty_assignment_ids = fields.One2many(
        "justech.purchase.sale.qty.assignment",
        "vendor_bill_line_id",
        string="Asignaciones venta (factura)",
    )

    def _justech_is_product_invoice_line(self):
        """Odoo 19 marca líneas de producto con display_type='product' (no False)."""
        self.ensure_one()
        return self.display_type in (False, "product") and bool(self.product_id)

    def _justech_is_vendor_bill_line(self):
        self.ensure_one()
        return (
            self.move_id.move_type in ("in_invoice", "in_refund")
            and self._justech_is_product_invoice_line()
        )

    def _justech_bill_qty_signed(self):
        """Cantidad documental (positiva). Notas de crédito usan abs(quantity)."""
        self.ensure_one()
        return abs(self.quantity or 0.0)

    def _justech_bill_amount_signed(self):
        self.ensure_one()
        return abs(self.price_subtotal or 0.0)

    def _justech_bill_qty_assigned(self, exclude_assignment_ids=None):
        self.ensure_one()
        exclude_assignment_ids = exclude_assignment_ids or []
        assigns = self.justech_bill_qty_assignment_ids.filtered(
            lambda a: a.state == "active"
            and a.id not in exclude_assignment_ids
            and not a.purchase_line_id
        )
        return sum(assigns.mapped("quantity"))

    def _justech_bill_amount_assigned(self, exclude_assignment_ids=None):
        self.ensure_one()
        exclude_assignment_ids = exclude_assignment_ids or []
        assigns = self.justech_bill_qty_assignment_ids.filtered(
            lambda a: a.state == "active"
            and a.id not in exclude_assignment_ids
            and not a.purchase_line_id
        )
        return sum(assigns.mapped("amount"))

    def _justech_bill_qty_available(self, exclude_assignment_ids=None):
        self.ensure_one()
        if not self._justech_is_vendor_bill_line() or self.move_id.state == "cancel":
            return 0.0
        # Si ya hay POL, la disponibilidad real es la de la POL (no doble fuente).
        if self.purchase_line_id:
            return self.purchase_line_id._justech_qty_available_to_assign(
                exclude_assignment_ids=exclude_assignment_ids
            )
        total = self._justech_bill_qty_signed()
        assigned = self._justech_bill_qty_assigned(
            exclude_assignment_ids=exclude_assignment_ids
        )
        return max(total - assigned, 0.0)

    def _justech_bill_amount_available(self, exclude_assignment_ids=None):
        self.ensure_one()
        if not self._justech_is_vendor_bill_line() or self.move_id.state == "cancel":
            return 0.0
        if self.purchase_line_id:
            # Monto restante proporcional a qty disponible de la POL.
            pol = self.purchase_line_id
            qty_total = pol.product_qty or 0.0
            if float_compare(qty_total, 0.0, precision_digits=4) <= 0:
                return 0.0
            avail_qty = pol._justech_qty_available_to_assign(
                exclude_assignment_ids=exclude_assignment_ids
            )
            unit = (self._justech_bill_amount_signed() / self._justech_bill_qty_signed()) if self._justech_bill_qty_signed() else 0.0
            # Prefer proportional to bill line amount by available qty
            bill_qty = self._justech_bill_qty_signed()
            if float_compare(bill_qty, 0.0, precision_digits=4) <= 0:
                return 0.0
            return max(
                self._justech_bill_amount_signed()
                * (min(avail_qty, bill_qty) / bill_qty),
                0.0,
            )
        total = self._justech_bill_amount_signed()
        assigned = self._justech_bill_amount_assigned(
            exclude_assignment_ids=exclude_assignment_ids
        )
        return max(total - assigned, 0.0)

    @api.model
    def _justech_vendor_bill_line_domain(self, company, products, partner=None):
        domain = [
            ("company_id", "=", company.id),
            ("display_type", "in", (False, "product")),
            ("product_id", "in", products.ids),
            ("move_id.move_type", "in", ("in_invoice", "in_refund")),
            ("move_id.state", "!=", "cancel"),
        ]
        if partner:
            domain.append(("move_id.partner_id", "=", partner.id))
        return domain
