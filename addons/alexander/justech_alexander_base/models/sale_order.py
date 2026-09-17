from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    dx_outgoing_picking_count = fields.Integer(
        string="Entregas de salida",
        compute="_compute_dx_outgoing_picking_count",
    )

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.client_order_ref and not vals.get("ref"):
            vals["ref"] = self.client_order_ref
        return vals

    def _dx_outgoing_pickings(self):
        """Outgoing deliveries already linked to this order. Never invents one."""
        self.ensure_one()
        if "picking_ids" not in self._fields:
            return self.env["stock.picking"]
        return self.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing" and p.state != "cancel"
        )

    @api.depends("picking_ids", "picking_ids.state", "picking_ids.picking_type_code")
    def _compute_dx_outgoing_picking_count(self):
        for order in self:
            if "picking_ids" not in order._fields:
                order.dx_outgoing_picking_count = 0
                continue
            order.dx_outgoing_picking_count = len(
                order.picking_ids.filtered(
                    lambda p: p.picking_type_code == "outgoing" and p.state != "cancel"
                )
            )

    def _dx_ensure_outgoing_pickings(self):
        """Relaunch native procurement only. Does not create disconnected moves."""
        self.ensure_one()
        lines = self.order_line.filtered(lambda line: not line.display_type)
        if hasattr(lines, "_action_launch_stock_rule"):
            lines._action_launch_stock_rule()
        return self._dx_outgoing_pickings()

    def action_dx_open_conduce(self):
        """Open or locate the delivery. Conduce is a logistics flow, not a print."""
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise UserError(
                _(
                    "Confirme el pedido antes de crear un Conduce. "
                    "No se generan entregas desde una cotización."
                )
            )
        pickings = self._dx_outgoing_pickings()
        if not pickings:
            pickings = self._dx_ensure_outgoing_pickings()
        if not pickings:
            raise UserError(
                _(
                    "Este pedido no genera entrega. Revise que tenga productos "
                    "inventariables y una ruta de inventario. No se creó un "
                    "albarán desconectado del pedido."
                )
            )
        xmlid = "stock.action_picking_tree_outgoing"
        if not self.env.ref(xmlid, raise_if_not_found=False):
            xmlid = "stock.act_stock_picking_out"
        if not self.env.ref(xmlid, raise_if_not_found=False):
            xmlid = "stock.action_picking_tree_all"
        action = dict(self.env["ir.actions.act_window"]._for_xml_id(xmlid))
        action["name"] = _("Conduce")
        action["target"] = "current"
        action["context"] = {
            "default_company_id": self.company_id.id,
            "default_origin": self.name,
        }
        action["domain"] = [("id", "in", pickings.ids)]
        if len(pickings) == 1:
            form = self.env.ref("stock.view_picking_form")
            action["res_id"] = pickings.id
            action["view_mode"] = "form"
            action["views"] = [(form.id, "form")]
            action.pop("domain", None)
        return action
