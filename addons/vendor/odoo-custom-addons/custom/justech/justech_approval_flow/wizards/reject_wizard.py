# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class JustechApprovalRejectWizard(models.TransientModel):
    _name = "justech.approval.reject.wizard"
    _description = "Rechazar aprobación Justech"

    request_id = fields.Many2one(
        "justech.approval.request", required=True, ondelete="cascade"
    )
    reason = fields.Text(string="Motivo del rechazo", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No hay solicitud."))
        self.request_id.action_reject(note=self.reason)
        return {"type": "ir.actions.act_window_close"}
