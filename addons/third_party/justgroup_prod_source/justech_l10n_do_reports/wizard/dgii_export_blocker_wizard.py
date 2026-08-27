# -*- coding: utf-8 -*-
from odoo import _, fields, models


class JustechDoDgiiExportBlockerWizard(models.TransientModel):
    _name = "justech.do.dgii.export.blocker.wizard"
    _description = "Asistente — bloqueo generación Excel DGII"

    report_id = fields.Many2one(
        "justech.do.fiscal.report",
        string="Reporte",
        required=True,
        readonly=True,
    )
    report_state = fields.Char(string="Estado reporte", readonly=True)
    valid_count = fields.Integer(string="Documentos válidos", readonly=True)
    pending_approval_count = fields.Integer(string="Pendientes aprobación", readonly=True)
    incomplete_count = fields.Integer(string="Incompletos", readonly=True)
    not_loaded = fields.Boolean(string="Sin líneas cargadas", readonly=True)
    needs_approval = fields.Boolean(string="Requiere aprobación", readonly=True)
    no_valid = fields.Boolean(string="Sin válidos", readonly=True)
    wrong_state = fields.Boolean(string="Estado incorrecto", readonly=True)
    blocking_line_ids = fields.Many2many(
        "justech.do.fiscal.report.line",
        "dgii_blocker_line_rel",
        "wizard_id",
        "line_id",
        string="Documentos bloqueantes",
        readonly=True,
    )
    summary_html = fields.Html(string="Resumen", compute="_compute_summary_html")

    def _state_label(self, state):
        labels = dict(self.report_id._fields["state"].selection)
        return labels.get(state, state or "")

    def _compute_summary_html(self):
        for wiz in self:
            rtype = wiz.report_id.report_type
            parts = [
                _("<p><strong>No es posible generar el Excel %(type)s.</strong></p>")
                % {"type": rtype},
                _("<p><strong>Qué ocurrió:</strong> el reporte no cumple las condiciones para exportar.</p>"),
            ]
            reasons = []
            actions = []

            if wiz.not_loaded:
                reasons.append(_("No se cargaron líneas de revisión fiscal para este período."))
                actions.append(_("Valide el período y guarde la revisión fiscal."))
            if wiz.needs_approval:
                reasons.append(
                    _("%(n)s exclusión(es) manual(es) esperan aprobación del supervisor.")
                    % {"n": wiz.pending_approval_count}
                )
                actions.append(_("Apruebe las exclusiones en Pendientes de aprobación."))
            elif wiz.pending_approval_count:
                reasons.append(
                    _("%(n)s documento(s) con exclusión pendiente de decisión.")
                    % {"n": wiz.pending_approval_count}
                )
            if wiz.no_valid and not wiz.not_loaded:
                reasons.append(_("No hay documentos válidos incluidos para exportar."))
                actions.append(_("Revise los documentos incompletos o excluidos en Revisión fiscal."))
            if wiz.incomplete_count:
                reasons.append(
                    _("%(n)s documento(s) incompletos bloquean la exportación.")
                    % {"n": wiz.incomplete_count}
                )
            if wiz.wrong_state and not wiz.needs_approval:
                reasons.append(
                    _("El reporte está en estado «%(state)s»; debe estar Validado o Aprobado.")
                    % {"state": wiz._state_label(wiz.report_state)}
                )
                actions.append(_("Complete el flujo de validación y aprobación."))

            if wiz.valid_count:
                parts.append(
                    _("<p>✓ %(n)s documento(s) válido(s) en el período.</p>") % {"n": wiz.valid_count}
                )

            if reasons:
                parts.append("<p><strong>Por qué bloquea:</strong></p><ul>")
                for reason in reasons:
                    parts.append(f"<li>✗ {reason}</li>")
                parts.append("</ul>")

            if wiz.blocking_line_ids:
                parts.append("<p><strong>Documentos que bloquean:</strong></p><ul>")
                for line in wiz.blocking_line_ids[:15]:
                    label = line.move_name or line.ncf or _("Sin nombre")
                    detail = line.exclusion_reason or line.error_message or line.fiscal_state
                    parts.append(
                        f"<li><strong>{label}</strong> — {detail or ''}</li>"
                    )
                if len(wiz.blocking_line_ids) > 15:
                    parts.append(
                        f"<li>… {_('y %(n)s más') % {'n': len(wiz.blocking_line_ids) - 15}}</li>"
                    )
                parts.append("</ul>")

            if actions:
                parts.append("<p><strong>Qué debe hacer:</strong></p><ul>")
                for action in actions:
                    parts.append(f"<li>{action}</li>")
                parts.append("</ul>")

            parts.append(_("<p><strong>Acciones disponibles:</strong></p>"))
            wiz.summary_html = "".join(parts)

    def action_go_fiscal_review(self):
        self.ensure_one()
        return self.report_id.action_open_fiscal_review()

    def action_go_pending_tray(self):
        self.ensure_one()
        return self.env.ref(
            "justech_l10n_do_reports.action_justech_do_fiscal_review_pending"
        ).read()[0]

    def action_view_blocked_documents(self):
        self.ensure_one()
        domain = [("report_id", "=", self.report_id.id)]
        if self.blocking_line_ids:
            domain = [("id", "in", self.blocking_line_ids.ids)]
        else:
            domain += [
                "|",
                ("fiscal_state", "=", "incomplete"),
                ("line_approval_state", "=", "pending"),
            ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos bloqueantes"),
            "res_model": "justech.do.fiscal.report.line",
            "view_mode": "list",
            "domain": domain,
            "context": {
                "list_view_ref": "justech_l10n_do_reports.view_justech_do_fiscal_report_line_review_tree",
            },
            "target": "current",
        }
