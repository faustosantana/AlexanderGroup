# -*- coding: utf-8 -*-
"""Framework fiscal DGII — workflow, bitácora y contadores unificados."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from markupsafe import Markup, escape

STATE_LABELS = {
    "draft": "Borrador",
    "validated": "Validado",
    "pending_approval": "Requiere aprobación",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "generated": "Generado",
    "done": "Generado",
}

AUDIT_LABELS = {
    "create": "Creación revisión",
    "validate": "Validación",
    "exclude": "Exclusión",
    "include": "Re-inclusión",
    "submit_approval": "Envío a aprobación",
    "approve": "Aprobación",
    "reject": "Rechazo",
    "correction": "Corrección solicitada",
    "generate": "Generación Excel",
    "reopen": "Reapertura",
    "state_change": "Cambio de estado",
}


class JustechDoFiscalReportWorkflow(models.Model):
    _inherit = "justech.do.fiscal.report"

    created_by_id = fields.Many2one(
        "res.users",
        string="Creado por",
        readonly=True,
        default=lambda self: self.env.user,
        copy=False,
    )
    has_pending_approval = fields.Boolean(
        string="Tiene pendientes de aprobación",
        compute="_compute_has_pending_approval",
        store=True,
        index=True,
    )
    review_approved_count = fields.Integer(
        string="Exclusiones aprobadas",
        compute="_compute_review_counts",
    )
    review_base_total = fields.Float(
        string="Base total retenida",
        digits=(16, 2),
        compute="_compute_review_counts",
    )
    review_withholding_total = fields.Float(
        string="Retención total",
        digits=(16, 2),
        compute="_compute_review_counts",
    )
    summary_text = fields.Text(
        string="Resumen unificado",
        compute="_compute_summary_text",
    )
    date_from_display = fields.Char(
        string="Desde (período)",
        compute="_compute_period_display",
    )
    date_to_display = fields.Char(
        string="Hasta (período)",
        compute="_compute_period_display",
    )

    @api.depends("date_from", "date_to")
    def _compute_period_display(self):
        for report in self:
            report.date_from_display = (
                report.date_from.strftime("%d/%m/%Y") if report.date_from else ""
            )
            report.date_to_display = (
                report.date_to.strftime("%d/%m/%Y") if report.date_to else ""
            )

    @api.depends("approval_ids.state", "line_ids.manual_exclusion", "line_ids.line_approval_state")
    def _compute_has_pending_approval(self):
        for report in self:
            pending_approvals = report.approval_ids.filtered(
                lambda a: a.state == "pending"
            )
            pending_lines = report.line_ids.filtered(
                lambda l: l.manual_exclusion and l.line_approval_state == "pending"
            )
            report.has_pending_approval = bool(pending_approvals or pending_lines)

    @api.depends(
        "line_ids",
        "line_ids.fiscal_state",
        "line_ids.include_in_report",
        "line_ids.line_approval_state",
        "line_ids.manual_exclusion",
        "line_ids.withholding_base",
        "line_ids.amount_withholding",
    )
    def _compute_review_counts(self):
        for report in self:
            lines = report.line_ids
            report.review_line_count = len(lines)
            included = lines.filtered(lambda l: l.include_in_report and l.fiscal_state == "valid")
            report.review_base_total = sum(included.mapped("withholding_base"))
            report.review_withholding_total = sum(included.mapped("amount_withholding"))
            report.review_valid_count = len(included)
            report.review_incomplete_count = len(
                lines.filtered(lambda l: l.fiscal_state == "incomplete")
            )
            report.review_excluded_count = len(
                lines.filtered(
                    lambda l: not l.include_in_report or l.fiscal_state == "excluded"
                )
            )
            report.review_cancelled_count = len(
                lines.filtered(lambda l: l.fiscal_state == "cancelled")
            )
            report.review_pending_approval_count = len(
                lines.filtered(
                    lambda l: l.manual_exclusion and l.line_approval_state == "pending"
                )
            )
            report.review_approved_count = len(
                lines.filtered(
                    lambda l: l.manual_exclusion and l.line_approval_state == "approved"
                )
            )

    @api.depends(
        "review_line_count",
        "review_valid_count",
        "review_incomplete_count",
        "review_excluded_count",
        "review_cancelled_count",
        "review_pending_approval_count",
        "review_approved_count",
    )
    def _compute_summary_text(self):
        for report in self:
            report.summary_text = _(
                "Documentos en período: %(all)s\n"
                "Válidos para exportar: %(valid)s\n"
                "Incompletos: %(incomplete)s\n"
                "Excluidos: %(excluded)s\n"
                "Anulados: %(cancelled)s\n"
                "Pendientes de aprobación: %(pending)s\n"
                "Exclusiones aprobadas: %(approved)s"
            ) % {
                "all": report.review_line_count,
                "valid": report.review_valid_count,
                "incomplete": report.review_incomplete_count,
                "excluded": report.review_excluded_count,
                "cancelled": report.review_cancelled_count,
                "pending": report.review_pending_approval_count,
                "approved": report.review_approved_count,
            }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("period_code") and vals.get("date_from"):
                vals["period_code"] = fields.Date.to_date(vals["date_from"]).strftime(
                    "%Y%m"
                )
            # Expandir a mes completo solo si no vienen fechas (rango personalizado).
            if vals.get("period_code") and not (
                vals.get("date_from") and vals.get("date_to")
            ):
                date_from, date_to = self.env[
                    "justech.do.dgii.period"
                ].period_bounds_from_code(vals["period_code"])
                vals["date_from"] = date_from
                vals["date_to"] = date_to
        reports = super().create(vals_list)
        for report in reports:
            report._sync_dates_from_period_code()
            report._post_workflow_event(
                "create",
                _("Revisión fiscal creada por %(user)s — período %(period)s.")
                % {"user": report.created_by_id.name, "period": report.period_code or ""},
            )
        return reports

    def write(self, vals):
        if vals.get("period_code") and not (
            vals.get("date_from") and vals.get("date_to")
        ):
            date_from, date_to = self.env[
                "justech.do.dgii.period"
            ].period_bounds_from_code(vals["period_code"])
            vals = dict(vals)
            vals["date_from"] = date_from
            vals["date_to"] = date_to
        if "state" in vals and not self.env.context.get("justech_skip_state_guard"):
            for report in self:
                if report.state != vals["state"]:
                    raise UserError(
                        _(
                            "No puede cambiar el estado manualmente. "
                            "Use los botones de acción del reporte."
                        )
                    )
        return super().write(vals)

    def _sync_dates_from_period_code(self):
        """Alinea al mes completo solo si el reporte no usa rango personalizado."""
        for report in self:
            if not report.period_code:
                continue
            date_from, date_to = self.env[
                "justech.do.dgii.period"
            ].period_bounds_from_code(report.period_code)
            if report.date_from and report.date_to and (
                report.date_from != date_from or report.date_to != date_to
            ):
                # Rango personalizado: conservar fechas.
                continue
            if report.date_from != date_from or report.date_to != date_to:
                super(JustechDoFiscalReportWorkflow, report).write(
                    {"date_from": date_from, "date_to": date_to}
                )

    def _state_label(self, state):
        return STATE_LABELS.get(state, state or "")

    def _post_workflow_event(
        self, event_type, description="", move=None, line=None, file_hash=False, file_name=False
    ):
        self.ensure_one()
        label = AUDIT_LABELS.get(event_type, event_type)
        body = Markup("<b>%(event)s</b><br/>%(user)s — %(when)s<br/>%(detail)s") % {
            "event": escape(label),
            "user": escape(self.env.user.display_name),
            "when": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "detail": escape(description or ""),
        }
        self.message_post(body=body)
        return self._log_audit(
            event_type,
            description,
            move=move,
            line=line,
            file_hash=file_hash,
            file_name=file_name,
        )

    def _transition_state(self, new_state, description="", audit_type="state_change"):
        for report in self:
            old_state = report.state
            if old_state == new_state:
                continue
            super(JustechDoFiscalReportWorkflow, report.with_context(
                justech_skip_state_guard=True
            )).write({"state": new_state})
            detail = description or _(
                "Estado: %(old)s → %(new)s"
            ) % {
                "old": report._state_label(old_state),
                "new": report._state_label(new_state),
            }
            report._post_workflow_event(audit_type, detail)

    def _refresh_summary_counts(self):
        """Unifica contadores almacenados con las líneas cargadas."""
        for report in self:
            lines = report.line_ids
            incomplete = lines.filtered(lambda l: l.fiscal_state == "incomplete")
            partners = set(incomplete.mapped("partner_id.id"))
            super(JustechDoFiscalReportWorkflow, report).write(
                {
                    "count_all": len(lines),
                    "count_valid": len(
                        lines.filtered(
                            lambda l: l.include_in_report and l.fiscal_state == "valid"
                        )
                    ),
                    "count_incomplete": len(incomplete),
                    "count_excluded": len(
                        lines.filtered(
                            lambda l: not l.include_in_report
                            or l.fiscal_state == "excluded"
                        )
                    ),
                    "count_cancelled": len(
                        lines.filtered(lambda l: l.fiscal_state == "cancelled")
                    ),
                    "count_partners_errors": len(partners),
                    "validation_log": report.summary_text,
                }
            )

    def _get_blocking_line_ids(self):
        self.ensure_one()
        lines = self.line_ids
        blocking = lines.filtered(
            lambda l: (
                (l.manual_exclusion and l.line_approval_state == "pending")
                or l.fiscal_state == "incomplete"
            )
        )
        if not blocking:
            blocking = lines.filtered(
                lambda l: not (l.include_in_report and l.fiscal_state == "valid")
                and l.fiscal_state != "cancelled"
            )
        return blocking

    def _get_export_diagnostics(self):
        self.ensure_one()
        lines = self.line_ids
        valid_lines = lines.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )
        pending_lines = lines.filtered(
            lambda l: l.manual_exclusion and l.line_approval_state == "pending"
        )
        incomplete_lines = lines.filtered(lambda l: l.fiscal_state == "incomplete")
        not_loaded = not lines
        needs_approval = bool(pending_lines) or self.state == "pending_approval"
        no_valid = not valid_lines
        wrong_state = self.state not in ("validated", "approved", "generated", "done")
        blocking_lines = self._get_blocking_line_ids()
        return {
            "valid_count": len(valid_lines),
            "pending_approval_count": len(pending_lines),
            "incomplete_count": len(incomplete_lines),
            "not_loaded": not_loaded,
            "needs_approval": needs_approval,
            "no_valid": no_valid,
            "wrong_state": wrong_state and not needs_approval,
            "state": self.state,
            "blocking_line_ids": blocking_lines.ids,
        }

    def action_open_export_blocker_wizard(self, diagnostics=None):
        self.ensure_one()
        diagnostics = diagnostics or self._get_export_diagnostics()
        return {
            "type": "ir.actions.act_window",
            "name": _("No es posible generar el Excel %(type)s") % {"type": self.report_type},
            "res_model": "justech.do.dgii.export.blocker.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.id,
                "default_valid_count": diagnostics["valid_count"],
                "default_pending_approval_count": diagnostics["pending_approval_count"],
                "default_incomplete_count": diagnostics["incomplete_count"],
                "default_not_loaded": diagnostics["not_loaded"],
                "default_needs_approval": diagnostics["needs_approval"],
                "default_no_valid": diagnostics["no_valid"],
                "default_wrong_state": diagnostics["wrong_state"],
                "default_report_state": self.state,
                "default_blocking_line_ids": [(6, 0, diagnostics["blocking_line_ids"])],
            },
        }

    @api.model
    def _archive_legacy_reports(self):
        """Archiva reportes pre-workflow del flujo activo sin borrar datos."""
        workflow_states = {
            "validated",
            "pending_approval",
            "approved",
            "rejected",
            "generated",
        }
        for report in self.sudo().search([("active", "=", True)]):
            legacy = False
            if report.state == "done" and not report.validated_by_id:
                legacy = True
            elif report.has_pending_approval and report.state not in workflow_states:
                legacy = True
            elif not report.period_code and report.generated_at:
                legacy = True
            if not legacy:
                continue
            report.with_context(justech_skip_state_guard=True).write({"active": False})
            if hasattr(report, "_post_workflow_event"):
                report._post_workflow_event(
                    "state_change",
                    _("Reporte legacy archivado del flujo activo (datos conservados)."),
                )

    def action_open_fiscal_review(self):
        form = self.env.ref(
            "justech_l10n_do_reports.view_justech_do_fiscal_report_review_form",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Revisión fiscal"),
            "res_model": "justech.do.fiscal.report",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(form.id, "form")] if form else False,
            "target": "current",
        }

    def action_open_pending_tray(self):
        return self.env.ref(
            "justech_l10n_do_reports.action_justech_do_fiscal_review_pending"
        ).read()[0]

    def action_generate(self, valid_moves=None):
        """Genera líneas exportables sin cambiar el estado del flujo fiscal."""
        for report in self:
            report.line_ids.unlink()
            lines = report._collect_lines(valid_moves=valid_moves)
            super(JustechDoFiscalReportWorkflow, report).write(
                {
                    "line_ids": [(0, 0, line) for line in lines],
                    "generated_at": fields.Datetime.now(),
                    "generated_by_id": self.env.user.id,
                }
            )
            report._refresh_summary_counts()
        return True


class JustechDoFiscalReportLineWorkflow(models.Model):
    _inherit = "justech.do.fiscal.report.line"

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No hay contacto vinculado."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_payment(self):
        self.ensure_one()
        payments = self.env["account.payment"]
        if self.payment_id:
            payments = self.payment_id
        elif self.move_id:
            payments = self.move_id._get_reconciled_payments()
        if not payments:
            raise UserError(_("Este documento no tiene pagos conciliados."))
        if len(payments) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "res_id": payments.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Pagos del documento"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", payments.ids)],
            "target": "current",
        }

    def action_view_move_pdf(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No hay documento vinculado."))
        try:
            report = self.env.ref("account.account_invoices")
        except ValueError:
            raise UserError(_("No se encontró el reporte PDF de facturas.")) from None
        return report.report_action(self.move_id)
