# -*- coding: utf-8 -*-
"""Línea de regularización fiscal (608 / 607 / IT-1) — período original."""
from odoo import _, api, fields, models


class JustechDoFiscalRegularization(models.Model):
    _name = "justech.do.fiscal.regularization"
    _description = "Regularización fiscal DGII (608 / 607 / IT-1)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "original_fiscal_period desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)

    company_id = fields.Many2one(
        "res.company", required=True, index=True, ondelete="restrict"
    )
    move_id = fields.Many2one(
        "account.move",
        string="Documento",
        required=True,
        index=True,
        ondelete="restrict",
    )
    ncf = fields.Char(string="NCF", index=True)
    document_type = fields.Char(string="Tipo documento")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    invoice_date = fields.Date(string="Fecha de factura")
    original_invoice_date = fields.Date(string="Fecha factura original")
    original_fiscal_period = fields.Char(
        string="Período fiscal original",
        size=6,
        index=True,
        help="YYYYMM — período del comprobante (no la fecha de cancelación).",
    )
    cancellation_execution_date = fields.Datetime(
        string="Fecha de cancelación interna"
    )
    regularization_creation_date = fields.Datetime(
        string="Fecha creación regularización",
        default=fields.Datetime.now,
    )

    # 608
    reporting_period_608 = fields.Char(
        string="Período 608",
        size=6,
        index=True,
        help="Debe coincidir con original_fiscal_period.",
    )
    annulment_type_608 = fields.Char(string="Tipo anulación 608")
    required_608 = fields.Boolean(string="608 requerido", default=True)
    status_608 = fields.Selection(
        selection=[
            ("pending", "Pendiente de incluir"),
            ("rectification_required", "Rectificativa requerida"),
            ("prepared", "Preparado"),
            ("exported", "Exportado"),
            ("presented", "Presentado"),
            ("accepted", "Aceptado"),
        ],
        string="Estado 608",
        default="pending",
        index=True,
    )

    # 607
    rectification_607_required = fields.Boolean(string="Rectificar 607")
    rectification_607_period = fields.Char(string="Período 607 a rectificar", size=6)
    status_607 = fields.Selection(
        selection=[
            ("na", "No aplica"),
            ("pending", "Pendiente de rectificar"),
            ("prepared", "Rectificativa preparada"),
            ("presented", "Rectificativa presentada"),
            ("accepted", "Rectificativa aceptada"),
        ],
        string="Estado 607",
        default="na",
    )

    # IT-1
    rectification_it1_required = fields.Boolean(string="Rectificar IT-1")
    rectification_it1_period = fields.Char(string="Período IT-1", size=6)
    status_it1 = fields.Selection(
        selection=[
            ("na", "No aplica"),
            ("validation_required", "Validación requerida"),
            ("pending", "Pendiente de rectificar"),
            ("rectified", "Rectificado"),
            ("accepted", "Aceptado"),
        ],
        string="Estado IT-1",
        default="na",
    )

    responsible_user_id = fields.Many2one("res.users", string="Responsable")
    activity_id = fields.Many2one("mail.activity", string="Actividad", copy=False)
    deadline = fields.Date(string="Fecha límite")
    cancellation_reason = fields.Text(string="Motivo")
    source_operation = fields.Selection(
        selection=[
            ("direct_cancel", "Cancelación directa"),
            ("cn_conversion", "Conversión NC→cancelación"),
            ("manual", "Manual"),
            ("historical_backfill", "Backfill histórico"),
        ],
        default="direct_cancel",
    )
    linked_regularization_ids = fields.Many2many(
        "justech.do.fiscal.regularization",
        "justech_do_fiscal_reg_link_rel",
        "reg_id",
        "linked_id",
        string="Regularizaciones vinculadas",
    )
    cancelled_by_user_id = fields.Many2one("res.users", string="Cancelado por")
    general_status = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("in_progress", "En proceso"),
            ("review_required", "Revisión requerida"),
            ("regularized", "Regularizado"),
            ("observations", "Con observaciones"),
        ],
        default="pending",
        index=True,
    )
    treatment_summary = fields.Char(
        string="Tratamiento visible",
        compute="_compute_treatment_summary",
        store=True,
    )
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    currency_id = fields.Many2one(related="move_id.currency_id")
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Evidencia / acuses",
    )
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "uniq_move_ncf_period",
            "unique(company_id, move_id, ncf, original_fiscal_period)",
            "Ya existe una regularización para este NCF y período.",
        ),
    ]

    @api.depends("move_id", "ncf", "original_fiscal_period")
    def _compute_display_name(self):
        for rec in self:
            parts = [
                rec.move_id.name or "",
                rec.ncf or "",
                rec.original_fiscal_period or "",
            ]
            rec.display_name = " / ".join(p for p in parts if p) or _("Regularización")

    @api.depends(
        "required_608",
        "reporting_period_608",
        "rectification_607_required",
        "rectification_607_period",
        "rectification_it1_required",
        "rectification_it1_period",
        "general_status",
    )
    def _compute_treatment_summary(self):
        for rec in self:
            period = rec.reporting_period_608 or rec.original_fiscal_period or ""
            label = self._format_period_label(period)
            parts = []
            if rec.rectification_607_required:
                parts.append(_("Rectificar 607 %s") % label)
            if rec.required_608:
                parts.append(_("Incluir en 608 %s") % label)
            if rec.rectification_it1_required:
                parts.append(_("Validar IT-1 %s") % label)
            if rec.general_status == "review_required":
                parts = [_("Revisión requerida — período a validar")]
            rec.treatment_summary = " + ".join(parts) if parts else _("Pendiente")

    @api.model
    def _format_period_label(self, period_code):
        code = (period_code or "").strip()
        if len(code) == 6 and code.isdigit():
            return "%s/%s" % (code[4:6], code[:4])
        return code or "—"

    def action_mark_608_prepared(self):
        self.write({"status_608": "prepared", "general_status": "in_progress"})
        return True

    def action_mark_608_presented(self):
        self.write({"status_608": "presented", "general_status": "in_progress"})
        return True

    def action_mark_608_accepted(self):
        for rec in self:
            vals = {"status_608": "accepted"}
            if (
                rec.status_607 in ("na", "accepted")
                and rec.status_it1 in ("na", "accepted", "rectified")
            ):
                vals["general_status"] = "regularized"
                if rec.activity_id:
                    rec.activity_id.action_feedback(
                        feedback=_("Regularización fiscal completada.")
                    )
            rec.write(vals)
        return True

    def action_mark_607_presented(self):
        self.write({"status_607": "presented", "general_status": "in_progress"})
        return True

    def action_mark_607_accepted(self):
        self.write({"status_607": "accepted"})
        return True

    def action_mark_it1_rectified(self):
        self.write({"status_it1": "rectified"})
        return True
