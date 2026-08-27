# -*- coding: utf-8 -*-
"""Fase 19.3 — Bandeja de revisión fiscal DGII (extiende justech.do.fiscal.report)."""
from __future__ import annotations

import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class JustechDoFiscalReportReview(models.Model):
    _name = "justech.do.fiscal.report"
    _inherit = ["justech.do.fiscal.report", "mail.thread", "mail.activity.mixin"]

    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("validated", "Validado"),
            ("pending_approval", "Requiere aprobación"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
            ("generated", "Generado"),
            ("done", "Generado"),
        ],
        string="Estado flujo",
        default="draft",
        tracking=True,
    )
    validated_by_id = fields.Many2one("res.users", string="Validado por", readonly=True)
    validated_at = fields.Datetime(string="Fecha validación", readonly=True)
    approved_by_id = fields.Many2one("res.users", string="Aprobado por", readonly=True)
    approved_at = fields.Datetime(string="Fecha aprobación", readonly=True)
    rejected_by_id = fields.Many2one("res.users", string="Rechazado por", readonly=True)
    rejected_at = fields.Datetime(string="Fecha rechazo", readonly=True)
    rejection_comment = fields.Text(string="Comentario de rechazo", readonly=True)
    export_file_hash = fields.Char(string="Hash Excel DGII", readonly=True)
    manual_exclusion_count = fields.Integer(
        string="Exclusiones manuales",
        compute="_compute_manual_exclusion_count",
    )
    pending_approval_count = fields.Integer(
        string="Aprobaciones pendientes",
        compute="_compute_manual_exclusion_count",
    )
    approval_ids = fields.One2many(
        "justech.do.dgii.report.approval",
        "report_id",
        string="Aprobaciones",
    )
    audit_ids = fields.One2many(
        "justech.do.dgii.report.audit",
        "report_id",
        string="Bitácora",
    )
    review_line_count = fields.Integer(
        string="Líneas revisión",
        compute="_compute_review_counts",
    )
    review_valid_count = fields.Integer(compute="_compute_review_counts")
    review_incomplete_count = fields.Integer(compute="_compute_review_counts")
    review_excluded_count = fields.Integer(compute="_compute_review_counts")
    review_cancelled_count = fields.Integer(compute="_compute_review_counts")
    review_pending_approval_count = fields.Integer(compute="_compute_review_counts")

    AUTO_UAT_EXCLUSION_REASON = (
        "Documento de prueba/UAT excluido del reporte fiscal."
    )

    @api.depends(
        "line_ids.manual_exclusion",
        "line_ids.line_approval_state",
        "approval_ids.state",
    )
    def _compute_manual_exclusion_count(self):
        for report in self:
            report.manual_exclusion_count = len(
                report.line_ids.filtered("manual_exclusion")
            )
            pending_lines = report.line_ids.filtered(
                lambda l: l.manual_exclusion and l.line_approval_state == "pending"
            )
            report.pending_approval_count = len(pending_lines)

    def _is_supervisor(self):
        return self.env.user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        )

    def _log_audit(self, event_type, description="", move=None, line=None, file_hash=False, file_name=False):
        self.ensure_one()
        return self.env["justech.do.dgii.report.audit"].sudo().create(
            {
                "report_id": self.id,
                "event_type": event_type,
                "user_id": self.env.user.id,
                "move_id": move.id if move else False,
                "line_id": line.id if line else False,
                "description": description,
                "file_hash": file_hash or False,
                "file_name": file_name or False,
            }
        )

    def _check_editable(self):
        self.ensure_one()
        if self.state in ("generated", "done"):
            raise UserError(_("El reporte ya fue generado. Solicite reapertura al supervisor."))

    def action_load_review_lines(self):
        """Carga todas las líneas del período para revisión en línea."""
        for report in self:
            report._check_editable()
            if report.date_from > report.date_to:
                raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))
            report.line_ids.unlink()
            lines = report._collect_review_lines()
            report.write({"line_ids": [(0, 0, vals) for vals in lines]})
            if lines:
                load_msg = _("Período cargado con %(n)s documento(s).") % {"n": len(lines)}
            else:
                load_msg = _(
                    "No se encontraron documentos para %(rtype)s en %(company)s "
                    "del %(dfrom)s al %(dto)s. "
                    "Causas frecuentes: sin retenciones con affects_623/código Gobierno, "
                    "fecha de retención fuera del período, pago sin vínculo a factura, "
                    "o empresa incorrecta."
                ) % {
                    "rtype": report.report_type,
                    "company": report.company_id.display_name,
                    "dfrom": report.date_from,
                    "dto": report.date_to,
                }
            report._transition_state(
                "draft",
                load_msg,
                audit_type="validate",
            )
            report._refresh_summary_counts()
            auto_excluded = report.line_ids.filtered("auto_exclusion")
            if auto_excluded:
                report._log_audit(
                    "exclude",
                    _(
                        "%(n)s documento(s) con exclusión automática visibles en revisión."
                    )
                    % {"n": len(auto_excluded)},
                )
            report._log_audit(
                "validate",
                _("Carga de %(n)s líneas para revisión.") % {"n": len(lines)},
            )
        return True

    def _collect_review_lines(self):
        self.ensure_one()
        if self.report_type == "606":
            return self._review_lines_606()
        if self.report_type == "607":
            return self._review_lines_607()
        if self.report_type == "608":
            return self._review_lines_608()
        if self.report_type == "623":
            return self._review_lines_623()
        return []

    def _review_lines_dgii(self, exporter_model):
        self.ensure_one()
        exporter = self.env[exporter_model]
        result = exporter.validate_period(
            self.company_id, self.date_from, self.date_to, refresh_states=True
        )
        return [
            self._prepare_line_vals_dgii(move, result, exporter)
            for move in result["buckets"]["all"]
        ]

    def _review_lines_606(self):
        return self._review_lines_dgii("justech.do.dgii.606.exporter")

    def _fdp(self):
        return self.env["justech.do.fiscal.data.provider"]

    def _prepare_line_vals_dgii(self, move, result, exporter):
        fdp = self._fdp()
        itbis = self._move_itbis_amount(move)
        wh_itbis, wh_isr, _wh_extra1, _wh_extra2 = exporter._withholding_breakdown(move)
        errors = result["move_errors"].get(move.id)
        if errors is None and move in result["buckets"]["incomplete"]:
            errors = exporter._dgii_validate_single_move(
                move, self.date_from, self.date_to
            )
        errors = errors or []
        pay_code = exporter._payment_method_code(move)
        partner = move.partner_id
        fiscal_state = move.justech_do_dgii_fiscal_state or "incomplete"
        exclusion_reason = move.justech_do_dgii_exclusion_reason or ""
        auto_exclusion = False
        fdp = self._fdp()
        if fiscal_state == "excluded" or not fdp.include_in_dgii(move):
            if not exclusion_reason:
                exclusion_reason = _(self.AUTO_UAT_EXCLUSION_REASON)
                auto_exclusion = True
            else:
                auto_exclusion = True
        include = fdp.include_in_dgii(move) and fiscal_state != "cancelled"
        return {
            "move_id": move.id,
            "move_name": move.name or move.ref,
            "partner_id": partner.id,
            "partner_vat": partner.justech_do_clean_vat()
            if hasattr(partner, "justech_do_clean_vat")
            else (partner.vat or ""),
            "partner_name": partner.display_name,
            "partner_id_type": partner.justech_do_partner_id_type or "",
            "document_type": fdp.get_document_type_prefix(move),
            "ncf": fdp.get_ncf(move),
            "ncf_modified": fdp.get_ncf_modified(move),
            "document_date": move.invoice_date,
            "invoice_date_due": move.invoice_date_due,
            "currency_id": move.currency_id.id,
            "amount_untaxed": abs(move.amount_untaxed_signed),
            "amount_tax": itbis,
            "amount_withholding": wh_itbis + wh_isr,
            "amount_total": abs(move.amount_total_signed),
            "payment_method_code": pay_code,
            "fiscal_state": fiscal_state,
            "include_in_report": include,
            "exclusion_reason": exclusion_reason,
            "auto_exclusion": auto_exclusion,
            "error_message": "\n".join(errors),
            "manual_exclusion": False,
        }

    def _prepare_line_vals_606(self, move, result, exporter):
        return self._prepare_line_vals_dgii(move, result, exporter)

    def _review_lines_607(self):
        return self._review_lines_dgii("justech.do.dgii.607.exporter")

    def _review_lines_608(self):
        self.ensure_one()
        exporter = self.env["justech.do.dgii.608.exporter"]
        result = exporter.validate_period(
            self.company_id, self.date_from, self.date_to, refresh_states=True
        )
        fdp = self._fdp()
        return [
            self._prepare_line_vals_generic(move)
            for move in result["buckets"]["all"]
            if fdp.get_ncf(move)
        ]

    def _review_lines_623(self):
        self.ensure_one()
        exporter = self.env["justech.do.dgii.623.exporter"]
        result = exporter.validate_period(
            self.company_id, self.date_from, self.date_to, refresh_states=True
        )
        return [
            self._prepare_line_vals_623(move, result, exporter)
            for move in result["buckets"]["all"]
        ]

    def _prepare_line_vals_623(self, move, result, exporter):
        fdp = self._fdp()
        gov_tax = exporter._gov_tax(self.company_id)
        gov_amt = exporter._gov_amount(move, gov_tax)
        errors = result["move_errors"].get(move.id)
        if errors is None and move in result["buckets"]["incomplete"]:
            errors = exporter._dgii_validate_single_move(
                move, self.date_from, self.date_to
            )
        errors = errors or []
        partner = move.partner_id
        fiscal_state = move.justech_do_dgii_fiscal_state or "incomplete"
        exclusion_reason = move.justech_do_dgii_exclusion_reason or ""
        auto_exclusion = False
        if fiscal_state == "excluded" or not fdp.include_in_dgii(move):
            if not exclusion_reason:
                exclusion_reason = _(self.AUTO_UAT_EXCLUSION_REASON)
            auto_exclusion = True
        include = fdp.include_in_dgii(move) and fiscal_state != "cancelled"
        ret_date = exporter._retention_date(move) or move.invoice_date
        payment = exporter._payment_with_gov_data(move)
        persistent = exporter._persistent_gov_lines(move=move)
        rate = 0.0
        base = abs(move.amount_untaxed_signed) if move.amount_untaxed_signed else abs(move.amount_untaxed)
        dgii_code = ""
        if persistent:
            rate = persistent[:1].rate or 0.0
            base = persistent[:1].base_amount or base
            dgii_code = persistent[:1].dgii_withholding_code or ""
            if not dgii_code and persistent[:1].catalog_id:
                dgii_code = persistent[:1].catalog_id.dgii_withholding_code or ""
        if not rate and gov_amt and base:
            rate = round(100.0 * gov_amt / base, 4)
        if not dgii_code:
            dgii_code = "07"
        inclusion = _("Retención Estado / Gobierno con importe registrado.")
        if payment:
            inclusion = _(
                "Retención Estado vinculada al pago %(pay)s."
            ) % {"pay": payment.name}
        return {
            "move_id": move.id,
            "move_name": move.name or move.ref,
            "payment_id": payment.id if payment else False,
            "partner_id": partner.id,
            "partner_vat": partner.justech_do_clean_vat()
            if hasattr(partner, "justech_do_clean_vat")
            else (partner.vat or ""),
            "partner_name": partner.display_name,
            "partner_id_type": partner.justech_do_partner_id_type or "",
            "document_type": fdp.get_document_type_prefix(move),
            "ncf": fdp.get_ncf(move),
            "ncf_modified": fdp.get_ncf_modified(move),
            "document_date": ret_date,
            "invoice_date_due": move.invoice_date_due,
            "currency_id": move.currency_id.id,
            "amount_untaxed": abs(move.amount_untaxed_signed),
            "amount_tax": 0.0,
            "withholding_base": base,
            "withholding_rate": rate,
            "amount_withholding": gov_amt,
            "amount_total": abs(move.amount_total_signed),
            "dgii_withholding_code": dgii_code,
            "inclusion_reason": inclusion,
            "payment_method_code": "",
            "fiscal_state": fiscal_state,
            "include_in_report": include,
            "exclusion_reason": exclusion_reason,
            "auto_exclusion": auto_exclusion,
            "error_message": "\n".join(errors),
        }

    def _prepare_line_vals_generic(self, move):
        fdp = self._fdp()
        itbis = self._move_itbis_amount(move)
        fiscal_state = move.justech_do_dgii_fiscal_state or "incomplete"
        if fdp.is_voided(move):
            fiscal_state = "cancelled"
        void_meta = fdp.get_void_metadata(move)
        return {
            "move_id": move.id,
            "move_name": move.name or move.ref,
            "partner_id": move.partner_id.id,
            "partner_vat": move.partner_id.vat or "",
            "partner_name": move.partner_id.display_name,
            "document_type": fdp.get_document_type_prefix(move),
            "ncf": fdp.get_ncf(move),
            "ncf_modified": fdp.get_ncf_modified(move),
            "document_date": void_meta["void_date"] or move.invoice_date,
            "invoice_date_due": move.invoice_date_due,
            "currency_id": move.currency_id.id,
            "amount_untaxed": abs(move.amount_untaxed_signed),
            "amount_tax": itbis,
            "amount_total": abs(move.amount_total_signed),
            "fiscal_state": fiscal_state,
            "include_in_report": fdp.include_in_dgii(move),
            "exclusion_reason": fdp.get_dgii_exclusion_reason(move),
        }

    def action_validate_period(self):
        for report in self:
            if not report.line_ids:
                report.action_load_review_lines()
            if report.report_type in report.DGII_EXPORTER_MODELS:
                report.action_validate()
            report.write(
                {
                    "validated_by_id": self.env.user.id,
                    "validated_at": fields.Datetime.now(),
                }
            )
            report._refresh_summary_counts()
            report._transition_state(
                "validated",
                report.validation_log or _("Validación completada."),
                audit_type="validate",
            )
        return True

    def action_submit_for_approval(self):
        for report in self:
            if not report.manual_exclusion_count:
                raise UserError(_("No hay exclusiones manuales que requieran aprobación."))
            for line in report.line_ids.filtered("manual_exclusion"):
                if line.line_approval_state in ("none", False):
                    line.line_approval_state = "pending"
                existing = report.approval_ids.filtered(
                    lambda a: a.line_id == line and a.state == "pending"
                )
                if not existing:
                    self.env["justech.do.dgii.report.approval"].sudo().create(
                        {
                            "report_id": report.id,
                            "line_id": line.id,
                            "exclusion_reason": line.exclusion_reason,
                            "requested_by_id": line.excluded_by_id.id or self.env.user.id,
                        }
                    )
            report._transition_state(
                "pending_approval",
                _("%(n)s exclusiones pendientes de aprobación.")
                % {"n": report.manual_exclusion_count},
                audit_type="submit_approval",
            )
            report._notify_supervisors_approval()
        return True

    def _notify_supervisors_approval(self):
        self.ensure_one()
        manager_group = self.env.ref(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        )
        supervisors = manager_group.user_ids
        body = _(
            "El reporte %(name)s requiere aprobación de exclusiones fiscales (%(n)s documento(s))."
        ) % {"name": self.name, "n": self.manual_exclusion_count}
        self.message_post(body=body, partner_ids=supervisors.partner_id.ids)
        for supervisor in supervisors:
            if supervisor == self.env.user:
                continue
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=supervisor.id,
                summary=_("Aprobar exclusiones DGII %(type)s") % {"type": self.report_type},
                note=body,
            )

    def action_approve_report(self):
        if not self._is_supervisor():
            raise AccessError(_("Solo el supervisor fiscal puede aprobar exclusiones."))
        for report in self:
            if report.state != "pending_approval":
                raise UserError(_("El reporte no está pendiente de aprobación."))
            now = fields.Datetime.now()
            report.approval_ids.filtered(lambda a: a.state == "pending").write(
                {
                    "state": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_at": now,
                }
            )
            report.line_ids.filtered("manual_exclusion").write(
                {
                    "line_approval_state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": now,
                }
            )
            report.write(
                {
                    "approved_by_id": self.env.user.id,
                    "approved_at": now,
                }
            )
            report._transition_state(
                "approved",
                _("Reporte aprobado para generación."),
                audit_type="approve",
            )
        return True

    def action_reject_report(self):
        if not self._is_supervisor():
            raise AccessError(_("Solo el supervisor fiscal puede rechazar exclusiones."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar exclusiones"),
            "res_model": "justech.do.dgii.report.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_report_id": self.id},
        }

    def _apply_rejection(self, comment):
        self.ensure_one()
        now = fields.Datetime.now()
        for line in self.line_ids.filtered("manual_exclusion"):
            line.action_restore_inclusion(comment=comment)
        self.approval_ids.filtered(lambda a: a.state == "pending").write(
            {
                "state": "rejected",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": now,
                "comment": comment,
            }
        )
        self.write(
            {
                "rejected_by_id": self.env.user.id,
                "rejected_at": now,
                "rejection_comment": comment,
            }
        )
        self._transition_state(
            "validated",
            _("Exclusiones rechazadas: %(comment)s") % {"comment": comment},
            audit_type="reject",
        )

    def _get_exportable_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )

    def action_export_dgii(self, moves=None):
        self.ensure_one()
        if moves is None and self.line_ids:
            diagnostics = self._get_export_diagnostics()
            if (
                diagnostics["not_loaded"]
                or diagnostics["needs_approval"]
                or diagnostics["no_valid"]
            ):
                return self.action_open_export_blocker_wizard(diagnostics)
        return super().action_export_dgii(moves=moves)

    def action_export_dgii_606(self, moves=None):
        return self.action_export_dgii(moves=moves)

    def _check_can_generate(self):
        self.ensure_one()
        if not self._is_supervisor():
            raise AccessError(
                _("Solo el supervisor fiscal puede generar el Excel DGII final.")
            )
        diagnostics = self._get_export_diagnostics()
        if (
            diagnostics["not_loaded"]
            or diagnostics["needs_approval"]
            or diagnostics["no_valid"]
            or (diagnostics["wrong_state"] and self.manual_exclusion_count)
        ):
            return self.action_open_export_blocker_wizard(diagnostics)
        exportable = self.line_ids.filtered(
            lambda l: l.include_in_report and l.fiscal_state == "valid"
        )
        if not exportable:
            return self.action_open_export_blocker_wizard(diagnostics)
        return exportable

    def action_generate_dgii_export(self):
        for report in self:
            exportable = report._check_can_generate()
            if isinstance(exportable, dict):
                return exportable
            moves = exportable.mapped("move_id")
            if report.report_type in report.DGII_EXPORTER_MODELS:
                action = report.action_export_dgii(moves=moves)
            else:
                report.action_generate(valid_moves=moves)
                action = report.action_export_xlsx()
            raw = base64.b64decode(report.export_file or b"")
            file_hash = hashlib.sha256(raw).hexdigest()
            report.write(
                {
                    "export_file_hash": file_hash,
                    "generated_at": fields.Datetime.now(),
                    "generated_by_id": self.env.user.id,
                }
            )
            report._transition_state(
                "generated",
                _("Excel DGII generado. Hash SHA-256: %(hash)s") % {"hash": file_hash},
                audit_type="generate",
            )
            report._log_audit(
                "generate",
                _("Archivo %(fname)s") % {"fname": report.export_filename},
                file_hash=file_hash,
                file_name=report.export_filename,
            )
        return action

    def action_reopen_report(self):
        if not self._is_supervisor():
            raise AccessError(_("Solo el supervisor fiscal puede reabrir reportes."))
        for report in self:
            report._transition_state(
                "validated",
                _("Reporte reabierto para corrección."),
                audit_type="reopen",
            )
        return True

    def action_open_exclude_wizard(self):
        self.ensure_one()
        line_ids = self.env.context.get("active_ids", [])
        return {
            "type": "ir.actions.act_window",
            "name": _("Excluir de DGII"),
            "res_model": "justech.do.dgii.report.exclude.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.id,
                "default_line_ids": [(6, 0, line_ids)],
            },
        }


class JustechDoFiscalReportLineReview(models.Model):
    _inherit = "justech.do.fiscal.report.line"

    include_in_report = fields.Boolean(string="Incluir", default=True)
    fiscal_state = fields.Selection(
        selection=[
            ("valid", "Válido"),
            ("incomplete", "Incompleto"),
            ("excluded", "Excluido"),
            ("cancelled", "Anulado"),
        ],
        string="Estado fiscal",
    )
    move_name = fields.Char(string="Documento")
    partner_id = fields.Many2one("res.partner", string="Contacto")
    partner_id_type = fields.Selection(
        selection=[
            ("1", "RNC"),
            ("2", "Cédula"),
            ("3", "Pasaporte"),
        ],
        string="Tipo identificación",
    )
    ncf_modified = fields.Char(string="NCF modificado")
    invoice_date_due = fields.Date(string="Vencimiento")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    amount_withholding = fields.Float(string="Monto retenido", digits=(16, 2))
    payment_id = fields.Many2one("account.payment", string="Pago", index=True)
    withholding_rate = fields.Float(string="Porcentaje retención", digits=(16, 4))
    withholding_base = fields.Float(string="Base sujeta a retención", digits=(16, 2))
    dgii_withholding_code = fields.Char(string="Código retención DGII")
    inclusion_reason = fields.Char(string="Motivo de inclusión")
    payment_method_code = fields.Char(string="Forma de pago")
    exclusion_reason = fields.Text(string="Motivo exclusión")
    auto_exclusion = fields.Boolean(string="Exclusión automática", default=False)
    manual_exclusion = fields.Boolean(string="Exclusión manual", default=False)
    excluded_by_id = fields.Many2one("res.users", string="Excluido por", readonly=True)
    excluded_at = fields.Datetime(string="Fecha exclusión", readonly=True)
    line_approval_state = fields.Selection(
        selection=[
            ("none", "N/A"),
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
        ],
        string="Estado aprobación línea",
        default="none",
    )
    approved_by_id = fields.Many2one("res.users", string="Aprobado por", readonly=True)
    approved_at = fields.Datetime(string="Fecha aprobación línea", readonly=True)
    error_message = fields.Text(string="Errores")

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No hay documento vinculado."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_exclude_line(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Excluir de DGII"),
            "res_model": "justech.do.dgii.report.exclude.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.report_id.id,
                "active_model": "justech.do.fiscal.report.line",
                "active_ids": self.ids,
            },
        }

    def action_restore_inclusion(self, comment=""):
        for line in self:
            move = line.move_id
            if move:
                move.write(
                    {
                        "justech_do_include_in_dgii": True,
                        "justech_do_dgii_exclusion_reason": False,
                    }
                )
                exporter = line.report_id._get_dgii_exporter()
                if exporter:
                    exporter._refresh_move_fiscal_state(
                        move, line.report_id.date_from, line.report_id.date_to
                    )
                if comment:
                    reinclusion_body = _(
                        "Documento re-incluido en reportes DGII. %(comment)s"
                    ) % {"comment": comment}
                else:
                    reinclusion_body = _("Documento re-incluido en reportes DGII.")
                move.message_post(body=reinclusion_body)
            line.write(
                {
                    "include_in_report": True,
                    "manual_exclusion": False,
                    "auto_exclusion": False,
                    "exclusion_reason": False,
                    "fiscal_state": move.justech_do_dgii_fiscal_state if move else "incomplete",
                    "line_approval_state": "rejected" if comment else "none",
                    "excluded_by_id": False,
                    "excluded_at": False,
                }
            )
            line.report_id._log_audit(
                "include",
                comment or _("Re-inclusión de %(doc)s") % {"doc": line.move_name},
                move=move,
                line=line,
            )
