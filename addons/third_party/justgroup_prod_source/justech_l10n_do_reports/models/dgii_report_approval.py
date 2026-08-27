# -*- coding: utf-8 -*-
from odoo import fields, models


class JustechDoDgiiReportApproval(models.Model):
    _name = "justech.do.dgii.report.approval"
    _description = "Aprobación exclusiones reporte DGII"
    _order = "create_date desc, id desc"

    report_id = fields.Many2one(
        "justech.do.fiscal.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
        index=True,
    )
    line_id = fields.Many2one(
        "justech.do.fiscal.report.line",
        string="Línea",
        ondelete="cascade",
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
        ],
        string="Estado",
        default="pending",
        required=True,
    )
    requested_by_id = fields.Many2one("res.users", string="Solicitado por", required=True)
    reviewed_by_id = fields.Many2one("res.users", string="Revisado por")
    reviewed_at = fields.Datetime(string="Fecha revisión")
    comment = fields.Text(string="Comentario supervisor")
    exclusion_reason = fields.Text(string="Motivo exclusión")
