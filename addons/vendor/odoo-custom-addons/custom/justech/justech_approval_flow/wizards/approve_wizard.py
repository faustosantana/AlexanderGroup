# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class JustechApprovalApproveWizard(models.TransientModel):
    _name = "justech.approval.approve.wizard"
    _description = "Aprobar solicitud Justech"

    request_id = fields.Many2one(
        "justech.approval.request", required=True, ondelete="cascade"
    )
    request_note = fields.Text(
        related="request_id.request_note", string="Comentario del solicitante"
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        compute="_compute_attachment_ids",
        string="Adjuntos",
    )
    note = fields.Text(string="Comentario del aprobador")

    def _compute_attachment_ids(self):
        for wiz in self:
            wiz.attachment_ids = wiz.request_id.attachment_ids

    def action_confirm_approve(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No hay solicitud."))
        self.request_id.action_approve(note=self.note)
        return {"type": "ir.actions.act_window_close"}
