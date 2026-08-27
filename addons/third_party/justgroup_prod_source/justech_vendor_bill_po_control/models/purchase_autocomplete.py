# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.justech_vendor_bill_po_control.models.constants import (
    VENDOR_BILL_MOVE_TYPES,
)


class AccountMovePurchaseAutocomplete(models.Model):
    """Reinforce Autocompletar OC: same partner/company, available qty, no cross-company."""

    _inherit = "account.move"

    @api.onchange("purchase_vendor_bill_id", "purchase_id")
    def _onchange_purchase_auto_complete(self):
        po = False
        if self.purchase_vendor_bill_id and self.purchase_vendor_bill_id.purchase_order_id:
            po = self.purchase_vendor_bill_id.purchase_order_id
        elif self.purchase_id:
            po = self.purchase_id
        if po:
            self._justech_assert_po_selectable(po)
        res = super()._onchange_purchase_auto_complete()
        # After linking a valid PO on a saved bill, drop pending approval request if any
        if self.has_valid_purchase_order and isinstance(self.id, int):
            self._justech_cancel_approval_request_due_to_po()
        return res

    def _justech_assert_po_selectable(self, po):
        self.ensure_one()
        if not po:
            return
        if po.company_id != self.company_id:
            raise UserError(
                _("La Orden de Compra pertenece a otra compañía (%(co)s).")
                % {"co": po.company_id.display_name}
            )
        if po.state == "cancel":
            raise UserError(_("No puede usar una Orden de Compra cancelada."))
        if po.state not in ("purchase", "done"):
            raise UserError(
                _("La Orden de Compra %(po)s no está confirmada.")
                % {"po": po.display_name}
            )
        if self.partner_id:
            bill_commercial = self.partner_id.commercial_partner_id
            po_commercial = po.partner_id.commercial_partner_id
            if bill_commercial != po_commercial:
                raise UserError(
                    _("La Orden de Compra seleccionada pertenece a un proveedor diferente.")
                )
        if not self._justech_po_has_available_qty(po):
            blocking = self._justech_po_blocking_bills(po)
            msg = _(
                "Esta Orden de Compra ya está completamente asociada a otra factura activa."
            )
            if blocking:
                msg = _("%(base)s Factura(s): %(bills)s") % {
                    "base": msg,
                    "bills": ", ".join(blocking.mapped("display_name")),
                }
            raise UserError(msg)

    @api.model
    def _justech_po_has_available_qty(self, po):
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        for line in po.order_line.filtered(lambda l: not l.display_type):
            available = line.qty_to_invoice
            # Discount quantities reserved by other draft bills (not yet in qty_invoiced)
            reserved = self._justech_po_line_draft_reserved_qty(line)
            free = available - reserved
            if float_compare(free, 0.0, precision_digits=precision) > 0:
                return True
        return False

    @api.model
    def _justech_po_line_draft_reserved_qty(self, po_line, exclude_move=None):
        domain = [
            ("purchase_line_id", "=", po_line.id),
            ("move_id.state", "=", "draft"),
            ("move_id.move_type", "in", list(VENDOR_BILL_MOVE_TYPES)),
            ("display_type", "=", False),
        ]
        if exclude_move:
            domain.append(("move_id", "!=", exclude_move.id))
        lines = self.env["account.move.line"].search(domain)
        return sum(lines.mapped("quantity"))

    @api.model
    def _justech_po_blocking_bills(self, po):
        """Active (posted/draft) bills that reference the PO."""
        return self.env["account.move"].search(
            [
                ("move_type", "in", list(VENDOR_BILL_MOVE_TYPES)),
                ("state", "in", ("draft", "posted")),
                ("invoice_line_ids.purchase_line_id.order_id", "=", po.id),
            ]
        )

    @api.onchange("partner_id")
    def _onchange_partner_id_clear_po_if_mismatch(self):
        res = {}
        parent = super()
        if hasattr(parent, "_onchange_partner_id"):
            res = parent._onchange_partner_id() or {}
        if not self.partner_id:
            return res
        linked = self.invoice_line_ids.filtered(lambda l: l.purchase_line_id)
        if not linked:
            return res
        commercial = self.partner_id.commercial_partner_id
        bad = linked.filtered(
            lambda l: l.purchase_line_id.order_id.partner_id.commercial_partner_id != commercial
        )
        if bad:
            self.invoice_line_ids = self.invoice_line_ids - bad
            warning = {
                "title": _("Proveedor cambiado"),
                "message": _(
                    "Se eliminaron las líneas vinculadas a Órdenes de Compra de otro proveedor. "
                    "Seleccione nuevamente una OC válida."
                ),
            }
            if isinstance(res, dict):
                res["warning"] = warning
            else:
                res = {"warning": warning}
        return res
