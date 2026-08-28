# -*- coding: utf-8 -*-
"""Log inmutable de cancelación directa / regularización fiscal."""
from odoo import fields, models


class JustechDoFiscalRegularizationLog(models.Model):
    _name = "justech.do.fiscal.regularization.log"
    _description = "Auditoría cancelación directa / regularización fiscal"
    _order = "id desc"
    _rec_name = "move_name"

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="restrict",
        index=True,
    )
    move_name = fields.Char(string="Número", required=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Cliente")
    ncf = fields.Char(string="NCF", index=True)
    user_id = fields.Many2one("res.users", string="Usuario", required=True)
    event_datetime = fields.Datetime(string="Fecha/hora", required=True, index=True)
    previous_state = fields.Char(string="Estado previo")
    previous_payment_state = fields.Char(string="Pago previo")
    previous_amount_total = fields.Float(string="Total previo")
    reason = fields.Text(string="Motivo")
    not_delivered_declared = fields.Boolean(string="Declaró no entrega")
    fiscal_treatment = fields.Char(string="Tratamiento fiscal previsto")
    fiscal_treatment_other = fields.Char(string="Detalle otro")
    evidence_reviewed = fields.Text(string="Evidencia revisada")
    method = fields.Selection(
        selection=[
            ("direct_cancel", "Cancelación directa"),
            ("regularization_update", "Actualización regularización"),
        ],
        required=True,
        default="direct_cancel",
    )
    fiscal_state_after = fields.Char(string="Estado fiscal posterior")
    session_info = fields.Char(
        string="Sesión / IP",
        help="Metadatos de sesión cuando la arquitectura lo permite.",
    )
