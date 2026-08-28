# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    justech_qty_assigned_to_sales = fields.Float(
        string="Ya asignada a ventas",
        compute="_compute_justech_assign_qty",
        digits="Product Unit of Measure",
    )
    justech_qty_available_to_assign = fields.Float(
        string="Disponible asignar",
        compute="_compute_justech_assign_qty",
        digits="Product Unit of Measure",
    )
    justech_qty_assignment_ids = fields.One2many(
        "justech.purchase.sale.qty.assignment",
        "purchase_line_id",
        string="Asignaciones venta",
    )

    def _justech_qty_assigned_to_sales(self, exclude_assignment_ids=None):
        """Active commercial claim on this POL.

        Canonical: ASG rows are source of truth when present.
        Bare ``sale_line_id`` M2O (no ASG) claims the full ``product_qty``.
        Context ``justech_skip_m2o_for_sale_line_id`` skips that M2O claim when
        validating an ASG that mirrors the same SOL (no double-count).
        """
        self.ensure_one()
        exclude_assignment_ids = exclude_assignment_ids or []
        assigns = self.justech_qty_assignment_ids.filtered(
            lambda a: a.state == "active" and a.id not in exclude_assignment_ids
        )
        if assigns:
            return sum(assigns.mapped("quantity"))
        if self.sale_line_id:
            skip_sol = self.env.context.get("justech_skip_m2o_for_sale_line_id")
            if skip_sol and self.sale_line_id.id == skip_sol:
                return 0.0
            return self.product_qty or 0.0
        return 0.0

    def _justech_qty_available_to_assign(self, exclude_assignment_ids=None):
        self.ensure_one()
        if self.state == "cancel" or self.order_id.state == "cancel":
            return 0.0
        assigned = self._justech_qty_assigned_to_sales(
            exclude_assignment_ids=exclude_assignment_ids
        )
        return max((self.product_qty or 0.0) - assigned, 0.0)

    @api.depends(
        "product_qty",
        "sale_line_id",
        "state",
        "order_id.state",
        "justech_qty_assignment_ids",
        "justech_qty_assignment_ids.quantity",
        "justech_qty_assignment_ids.state",
    )
    def _compute_justech_assign_qty(self):
        for line in self:
            assigned = line._justech_qty_assigned_to_sales()
            line.justech_qty_assigned_to_sales = assigned
            line.justech_qty_available_to_assign = max(
                (line.product_qty or 0.0) - assigned, 0.0
            ) if line.state != "cancel" and line.order_id.state != "cancel" else 0.0

    def justech_link_to_sale_line(self, sale_line, quantity, allow_split=True):
        """Link this POL to a SOL for `quantity` without rewriting accounting.

        Returns True on success.
        """
        self.ensure_one()
        sale_line.ensure_one()
        if self.company_id != sale_line.company_id:
            raise UserError(_("No se puede relacionar una OC de otra compañía."))
        if self.order_id.state == "cancel" or self.state == "cancel":
            raise UserError(_("No se puede relacionar una OC cancelada."))
        if self.product_id != sale_line.product_id:
            raise UserError(_("El producto no coincide con la línea de venta."))
        avail = self._justech_qty_available_to_assign()
        if float_compare(quantity, 0.0, precision_digits=4) <= 0:
            raise UserError(_("La cantidad a asignar debe ser positiva."))
        if float_compare(quantity, avail, precision_digits=4) > 0:
            raise UserError(
                _("Cantidad %(qty)s supera el disponible %(avail)s.")
                % {"qty": quantity, "avail": avail}
            )
        sale_line.invalidate_recordset(["justech_qty_pending_purchase"])
        sale_line._compute_justech_purchase_coverage()
        pending = sale_line.justech_qty_pending_purchase or 0.0
        if float_compare(quantity, pending, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No puede relacionar %(qty)s unidades de %(product)s. "
                    "Solo quedan %(pending)s unidades pendientes de compra."
                )
                % {
                    "qty": quantity,
                    "product": sale_line.product_id.display_name,
                    "pending": pending,
                }
            )

        editable = self.order_id.state in ("draft", "sent", "to approve")
        billed_or_received = (
            float_compare(self.qty_invoiced or 0.0, 0.0, precision_digits=4) > 0
            or float_compare(self.qty_received or 0.0, 0.0, precision_digits=4) > 0
        )

        # Full remaining qty and empty sale_line_id → direct M2O
        if (
            not self.sale_line_id
            and float_compare(quantity, self.product_qty, precision_digits=4) == 0
            and not self.justech_qty_assignment_ids.filtered(lambda a: a.state == "active")
        ):
            self.sale_line_id = sale_line.id
            return True

        # Split editable draft POL
        if (
            allow_split
            and editable
            and not billed_or_received
            and not self.sale_line_id
            and float_compare(quantity, self.product_qty, precision_digits=4) < 0
        ):
            remaining = self.product_qty - quantity
            self.write({"product_qty": remaining})
            self.copy(
                {
                    "product_qty": quantity,
                    "sale_line_id": sale_line.id,
                    "order_id": self.order_id.id,
                }
            )
            return True

        # Safe commercial assignment (historical / billed / already linked)
        self.env["justech.purchase.sale.qty.assignment"].create(
            {
                "company_id": self.company_id.id,
                "purchase_line_id": self.id,
                "sale_line_id": sale_line.id,
                "quantity": quantity,
                "state": "active",
                "note": _("Relación comercial sin alterar contabilidad"),
            }
        )
        # If empty sale_line_id and assigning full available after previous assigns —
        # do not force wrong M2O when split across sales.
        if (
            not self.sale_line_id
            and float_compare(
                self._justech_qty_assigned_to_sales(),
                self.product_qty,
                precision_digits=4,
            )
            == 0
            and len(
                self.justech_qty_assignment_ids.filtered(lambda a: a.state == "active")
            )
            == 1
        ):
            # Single assignment covering full line → also set sale_line_id
            self.sale_line_id = sale_line.id
        return True
