# -*- coding: utf-8 -*-
from odoo import fields, models


class JustechDoDgiiReportAudit(models.Model):
    _name = "justech.do.dgii.report.audit"
    _description = "Bitácora auditoría reporte DGII"
    _order = "create_date desc, id desc"

    report_id = fields.Many2one(
        "justech.do.fiscal.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        selection=[
            ("create", "Creación revisión"),
            ("validate", "Validación"),
            ("exclude", "Exclusión"),
            ("include", "Re-inclusión"),
            ("submit_approval", "Envío a aprobación"),
            ("approve", "Aprobación"),
            ("reject", "Rechazo"),
            ("correction", "Corrección solicitada"),
            ("generate", "Generación Excel"),
            ("reopen", "Reapertura"),
            ("state_change", "Cambio de estado"),
        ],
        string="Evento",
        required=True,
    )
    user_id = fields.Many2one("res.users", string="Usuario", required=True)
    move_id = fields.Many2one("account.move", string="Documento")
    line_id = fields.Many2one("justech.do.fiscal.report.line", string="Línea reporte")
    description = fields.Text(string="Detalle")
    file_hash = fields.Char(string="Hash archivo")
    file_name = fields.Char(string="Nombre archivo")
