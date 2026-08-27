# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechApprovalSaleConfirmWizard(models.TransientModel):
    _name = "justech.approval.sale.confirm.wizard"
    _description = "Solicitud de aprobación con comentario y adjuntos"

    sale_order_id = fields.Many2one("sale.order", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", readonly=True)
    move_id = fields.Many2one("account.move", readonly=True)
    message = fields.Text(readonly=True)
    request_note = fields.Text(
        string="Comentario",
        help="Explique brevemente lo que desea que el aprobador revise.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "justech_approval_request_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Adjuntar archivos",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("purchase_order_id"):
            if self.env.context.get("justech_approval_rerequest"):
                res["message"] = _(
                    "La aprobación anterior ya no es válida porque la orden fue "
                    "modificada. Solicite aprobación nuevamente con el total y "
                    "líneas actuales."
                )
            else:
                res["message"] = _("Esta orden de compra requiere aprobación.")
        elif res.get("move_id"):
            res["message"] = _("Esta factura requiere aprobación antes de confirmarse.")
        else:
            res["message"] = _(
                "Esta cotización requiere aprobación antes de confirmarse."
            )
        return res

    def action_request_approval(self):
        self.ensure_one()
        note = (self.request_note or "").strip() or None
        attachments = self.attachment_ids
        if self.sale_order_id:
            self.sale_order_id.action_justech_request_approval(
                note=note, attachment_ids=attachments
            )
        elif self.purchase_order_id:
            self.purchase_order_id.action_justech_request_approval(
                note=note, attachment_ids=attachments
            )
        elif self.move_id:
            self.move_id.action_justech_request_approval(
                note=note, attachment_ids=attachments
            )
        else:
            raise UserError(_("No hay un documento para solicitar aprobación."))
        return {"type": "ir.actions.act_window_close"}
