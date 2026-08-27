# -*- coding: utf-8 -*-
"""Bandeja global de aprobación DGII para supervisores."""
from __future__ import annotations

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class JustechDoFiscalReportPendingTray(models.Model):
    _inherit = "justech.do.fiscal.report"

    approval_submitted_by_id = fields.Many2one(
        "res.users",
        string="Enviado por",
        readonly=True,
        copy=False,
    )
    approval_submitted_at = fields.Datetime(
        string="Fecha envío a aprobación",
        readonly=True,
        copy=False,
    )

    def _require_supervisor(self):
        if not self._is_supervisor():
            raise AccessError(_("Solo el supervisor fiscal puede realizar esta acción."))

    def _pending_approval_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.manual_exclusion and l.line_approval_state == "pending"
        )

    def _sync_approval_state(self):
        """Actualiza el estado del reporte según decisiones pendientes/resueltas."""
        for report in self:
            pending_approvals = report.approval_ids.filtered(
                lambda a: a.state == "pending"
            )
            pending_lines = report._pending_approval_lines()
            if pending_approvals or pending_lines:
                if report.state != "pending_approval":
                    report._transition_state(
                        "pending_approval",
                        _("Quedan documentos pendientes de aprobación."),
                        audit_type="state_change",
                    )
                continue

            approved_manual = report.line_ids.filtered(
                lambda l: l.manual_exclusion and l.line_approval_state == "approved"
            )
            if approved_manual:
                report.write(
                    {
                        "approved_by_id": report.approved_by_id.id
                        or self.env.user.id,
                        "approved_at": report.approved_at or fields.Datetime.now(),
                    }
                )
                report._transition_state(
                    "approved",
                    _("Todas las exclusiones pendientes fueron resueltas."),
                    audit_type="approve",
                )
            elif report.state == "pending_approval":
                report._transition_state(
                    "validated",
                    _("Exclusiones revisadas — reporte devuelto para corrección."),
                    audit_type="state_change",
                )

    def action_submit_for_approval(self):
        for report in self:
            if not report.approval_submitted_at:
                report.write(
                    {
                        "approval_submitted_by_id": self.env.user.id,
                        "approval_submitted_at": fields.Datetime.now(),
                    }
                )
        return super().action_submit_for_approval()

    def action_approve_report(self):
        self._require_supervisor()
        res = super().action_approve_report()
        self._sync_approval_state()
        return res

    def _notify_fiscal_correction(self, body):
        self.ensure_one()
        fiscal_user = self.approval_submitted_by_id or self.created_by_id
        if not fiscal_user:
            return
        self.message_post(body=body, partner_ids=fiscal_user.partner_id.ids)
        if fiscal_user != self.env.user:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=fiscal_user.id,
                summary=_("Corrección solicitada — %(type)s %(period)s")
                % {"type": self.report_type, "period": self.period_code or ""},
                note=body,
            )

    def _apply_line_decision(self, lines, comment="", mode="reject"):
        self.ensure_one()
        self._require_supervisor()
        now = fields.Datetime.now()
        correction_messages = []
        for line in lines:
            if line.line_approval_state != "pending":
                continue
            approvals = self.approval_ids.filtered(
                lambda a: a.line_id == line and a.state == "pending"
            )
            if mode == "correction":
                line.action_restore_inclusion(comment=comment)
                event = "correction"
                msg = _("Corrección solicitada para %(doc)s: %(comment)s") % {
                    "doc": line.move_name,
                    "comment": comment,
                }
                correction_messages.append(msg)
            else:
                line.action_restore_inclusion(comment=comment)
                event = "reject"
                msg = _("Exclusión rechazada para %(doc)s: %(comment)s") % {
                    "doc": line.move_name,
                    "comment": comment,
                }
            approvals.write(
                {
                    "state": "rejected",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_at": now,
                    "comment": comment,
                }
            )
            line.write({"line_approval_state": "rejected"})
            self._post_workflow_event(event, msg, move=line.move_id, line=line)
        if mode == "correction" and correction_messages:
            self._notify_fiscal_correction("<br/>".join(correction_messages))
        self._sync_approval_state()
        self._refresh_summary_counts()

    def _apply_rejection(self, comment):
        lines = self._pending_approval_lines()
        if lines:
            self._apply_line_decision(lines, comment=comment, mode="reject")
            return
        super()._apply_rejection(comment)

    def action_open_full_review(self):
        self.ensure_one()
        return self.action_open_fiscal_review()


class JustechDoFiscalReportLinePendingTray(models.Model):
    _inherit = "justech.do.fiscal.report.line"

    def _require_supervisor_line(self):
        if not self.env.user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        ):
            raise AccessError(_("Solo el supervisor fiscal puede aprobar exclusiones."))

    def action_approve_line(self):
        self._require_supervisor_line()
        now = fields.Datetime.now()
        for line in self:
            if line.line_approval_state != "pending":
                raise UserError(
                    _("La línea %(doc)s no está pendiente de aprobación.")
                    % {"doc": line.move_name}
                )
            approvals = line.report_id.approval_ids.filtered(
                lambda a: a.line_id == line and a.state == "pending"
            )
            approvals.write(
                {
                    "state": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_at": now,
                }
            )
            line.write(
                {
                    "line_approval_state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": now,
                }
            )
            line.report_id._post_workflow_event(
                "approve",
                line.exclusion_reason or _("Exclusión aprobada: %(doc)s") % {"doc": line.move_name},
                move=line.move_id,
                line=line,
            )
            line.report_id._sync_approval_state()
        return True

    def action_reject_line(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar exclusión"),
            "res_model": "justech.do.dgii.report.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.report_id.id,
                "default_line_ids": [(6, 0, self.ids)],
                "default_action_mode": "reject",
            },
        }

    def action_request_correction_line(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitar corrección"),
            "res_model": "justech.do.dgii.report.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.report_id.id,
                "default_line_ids": [(6, 0, self.ids)],
                "default_action_mode": "correction",
            },
        }
