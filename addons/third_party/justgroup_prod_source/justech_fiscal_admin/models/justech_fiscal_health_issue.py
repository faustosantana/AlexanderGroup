# -*- coding: utf-8 -*-
"""Detalle de hallazgos de Salud Fiscal (solo lectura operativa)."""
from odoo import fields, models


class JustechFiscalHealthIssue(models.TransientModel):
    _name = "justech.fiscal.health.issue"
    _description = "Hallazgo Salud Fiscal Justech"
    _order = "severity_rank, company_id, id"

    center_id = fields.Many2one("justech.fiscal.admin.center", ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Empresa", required=True)
    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    severity = fields.Selection(
        [
            ("critical", "Crítico"),
            ("high", "Alto"),
            ("medium", "Medio"),
            ("low", "Bajo"),
            ("info", "Informativo"),
        ],
        required=True,
        default="medium",
    )
    severity_rank = fields.Integer(default=50)
    impact = fields.Char(string="Impacto")
    cause = fields.Text(string="Causa")
    model_name = fields.Char(string="Modelo")
    res_model = fields.Char()
    res_id = fields.Integer()
    recommended_action = fields.Text(string="Acción recomendada")
    detected_at = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    state = fields.Selection(
        [("open", "Abierto"), ("ack", "Reconocido"), ("resolved", "Resuelto")],
        default="open",
        string="Estado",
    )
    category = fields.Selection(
        [
            ("error", "Error"),
            ("warning", "Advertencia"),
            ("info", "Información"),
        ],
        default="error",
    )

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
