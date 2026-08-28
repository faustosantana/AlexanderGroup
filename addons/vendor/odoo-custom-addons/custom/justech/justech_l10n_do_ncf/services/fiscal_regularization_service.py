# -*- coding: utf-8 -*-
"""Servicio: crear regularización fiscal post-cancelación (período original)."""
from datetime import timedelta

from odoo import _, api, fields, models


class JustechDoFiscalRegularizationService(models.AbstractModel):
    _name = "justech.do.fiscal.regularization.service"
    _description = "Justech DO — regularización fiscal automática"

    @api.model
    def period_code_from_date(self, day):
        day = fields.Date.to_date(day)
        if not day:
            return False
        return day.strftime("%Y%m")

    @api.model
    def format_period_label(self, period_code):
        code = (period_code or "").strip()
        if len(code) == 6 and code.isdigit():
            return "%s/%s" % (code[4:6], code[:4])
        return code or "—"

    def _find_607_report_period(self, move):
        """Período real del 607 donde aparece el move, si existe el modelo."""
        if "justech.do.fiscal.report.line" not in self.env:
            return False, False
        Line = self.env["justech.do.fiscal.report.line"].sudo()
        lines = Line.search(
            [
                ("move_id", "=", move.id),
                ("report_id.report_type", "=", "607"),
                ("include_in_report", "=", True),
            ],
            order="id desc",
            limit=5,
        )
        for line in lines:
            report = line.report_id
            if report.state in (
                "generated",
                "done",
                "approved",
                "pending_approval",
                "validated",
            ):
                return True, report.period_code or False
        if lines:
            return True, lines[0].report_id.period_code or False
        return False, False

    def _608_already_presented(self, company, period_code):
        if "justech.do.fiscal.report" not in self.env or not period_code:
            return False
        Report = self.env["justech.do.fiscal.report"].sudo()
        return bool(
            Report.search(
                [
                    ("company_id", "=", company.id),
                    ("report_type", "=", "608"),
                    ("period_code", "=", period_code),
                    ("state", "in", ("generated", "done", "approved")),
                ],
                limit=1,
            )
        )

    def _evaluate_it1_impact(self, move):
        """Heurística: ventas con impuestos / total > 0 → validar IT-1."""
        if move.move_type not in ("out_invoice", "out_refund"):
            return False
        if abs(move.amount_total or 0.0) > 0:
            return True
        if any(getattr(line, "tax_ids", False) for line in move.invoice_line_ids):
            return True
        return False

    def _valid_period_code(self, code):
        code = (code or "").strip()
        if len(code) == 6 and code.isdigit():
            return code
        return False

    def resolve_original_period(self, move):
        """Orden: 607 real → original_fiscal_period → 608_reporting_period → invoice_date.

        Nunca void_date / write_date / create_date / fecha de ejecución.
        """
        found_607, period_607 = self._find_607_report_period(move)
        invoice_date = move.invoice_date or move.date
        period_from_invoice = self.period_code_from_date(invoice_date)
        if found_607 and period_607:
            return {
                "original_fiscal_period": period_607,
                "invoice_date": invoice_date,
                "was_in_607": True,
                "period_source": "607_report",
                "review_required": False,
            }
        persisted_orig = self._valid_period_code(
            getattr(move, "justech_do_original_fiscal_period", False)
        )
        if persisted_orig:
            return {
                "original_fiscal_period": persisted_orig,
                "invoice_date": invoice_date,
                "was_in_607": bool(move.justech_do_included_in_607),
                "period_source": "original_fiscal_period",
                "review_required": False,
            }
        persisted_608 = self._valid_period_code(
            getattr(move, "justech_do_608_reporting_period", False)
        )
        if persisted_608:
            return {
                "original_fiscal_period": persisted_608,
                "invoice_date": invoice_date,
                "was_in_607": bool(move.justech_do_included_in_607),
                "period_source": "608_reporting_period",
                "review_required": False,
            }
        if move.justech_do_included_in_607:
            return {
                "original_fiscal_period": period_from_invoice,
                "invoice_date": invoice_date,
                "was_in_607": True,
                "period_source": "included_flag",
                "review_required": not bool(period_from_invoice),
            }
        if period_from_invoice:
            return {
                "original_fiscal_period": period_from_invoice,
                "invoice_date": invoice_date,
                "was_in_607": False,
                "period_source": "invoice_date",
                "review_required": False,
            }
        return {
            "original_fiscal_period": False,
            "invoice_date": invoice_date,
            "was_in_607": False,
            "period_source": "unknown",
            "review_required": True,
        }

    def resolve_annulment_type_608(self, move):
        """No inventar motivo. Orden: cancel_type → void evidence → vacío."""
        cancel_type = (move.justech_do_ncf_cancel_type or "").strip()
        if cancel_type:
            return cancel_type, False
        if "l10n_do_cancellation_type" in move._fields:
            latam = move.l10n_do_cancellation_type
            if latam:
                code = str(latam).strip()
                if len(code) == 1 and code.isdigit():
                    code = code.zfill(2)
                if code:
                    return code, False
        fdp = self.env["justech.do.fiscal.data.provider"]
        from_fdp = (fdp.get_cancellation_type(move) or "").strip()
        if from_fdp:
            if len(from_fdp) == 1 and from_fdp.isdigit():
                from_fdp = from_fdp.zfill(2)
            return from_fdp, False
        return False, True

    def find_existing_regularization(self, move, ncf, period):
        Reg = self.env["justech.do.fiscal.regularization"]
        domain = [
            ("company_id", "=", move.company_id.id),
            ("ncf", "=", ncf or False),
            ("original_fiscal_period", "=", period or False),
        ]
        existing = Reg.search(domain + [("move_id", "=", move.id)], limit=1)
        if existing:
            return existing
        return Reg.search(domain, limit=1)

    def create_historical_regularization(self, move, *, cancelled_by=None):
        """Backfill idempotente: crea reg faltante sin tocar asiento/NCF/secuencias.

        Solo escribe metadatos fiscales en el move si los períodos están vacíos
        y el enlace a la regularización.
        """
        move.ensure_one()
        ncf = (
            move._justech_get_issued_ncf()
            if hasattr(move, "_justech_get_issued_ncf")
            else (move.justech_do_ncf or False)
        )
        resolved = self.resolve_original_period(move)
        period = resolved["original_fiscal_period"]
        if not ncf or not period:
            return self.env["justech.do.fiscal.regularization"]

        existing = self.find_existing_regularization(move, ncf, period)
        if existing:
            if (
                hasattr(move, "justech_do_fiscal_regularization_id")
                and not move.justech_do_fiscal_regularization_id
            ):
                move.write({"justech_do_fiscal_regularization_id": existing.id})
            return existing

        annulment, reason_review = self.resolve_annulment_type_608(move)
        was_in_607 = resolved["was_in_607"]
        review = resolved["review_required"] or reason_review
        status_608 = "pending"
        if period and self._608_already_presented(move.company_id, period):
            status_608 = "rectification_required"
        it1 = self._evaluate_it1_impact(move)
        responsible = (
            move.company_id.justech_do_fiscal_regularization_user_id
            or move.justech_do_regularization_responsible_id
            or cancelled_by
            or self.env.user
        )
        cancel_dt = False
        if move.justech_do_ncf_void_date:
            from datetime import datetime as dt_cls

            void_day = fields.Date.to_date(move.justech_do_ncf_void_date)
            cancel_dt = dt_cls.combine(void_day, dt_cls.min.time().replace(hour=12))
        elif getattr(move, "justech_do_cancellation_execution_date", False):
            cancel_dt = move.justech_do_cancellation_execution_date

        vals = {
            "company_id": move.company_id.id,
            "move_id": move.id,
            "ncf": ncf,
            "document_type": move.move_type,
            "partner_id": move.partner_id.id,
            "invoice_date": resolved["invoice_date"],
            "original_invoice_date": resolved["invoice_date"],
            "original_fiscal_period": period,
            "cancellation_execution_date": cancel_dt or False,
            "reporting_period_608": period,
            "annulment_type_608": annulment or False,
            "required_608": True,
            "status_608": status_608,
            "rectification_607_required": bool(was_in_607 and period),
            "rectification_607_period": period if was_in_607 else False,
            "status_607": "pending" if was_in_607 else "na",
            "rectification_it1_required": bool(it1 and period),
            "rectification_it1_period": period if it1 else False,
            "status_it1": "validation_required" if it1 else "na",
            "responsible_user_id": responsible.id if responsible else False,
            "cancellation_reason": move.justech_do_direct_cancel_reason
            or move.justech_do_ncf_void_reason
            or False,
            "source_operation": "historical_backfill",
            "cancelled_by_user_id": (cancelled_by or self.env.user).id,
            "general_status": "review_required" if review else "pending",
            "amount_total": move.amount_total,
            "deadline": fields.Date.context_today(move) + timedelta(days=15),
            "notes": _("Creada por sincronización de anulaciones históricas."),
        }
        reg = self.env["justech.do.fiscal.regularization"].create(vals)

        # Metadatos fiscales mínimos (no toca state/NCF/asiento/secuencias)
        move_vals = {}
        if hasattr(move, "justech_do_fiscal_regularization_id"):
            move_vals["justech_do_fiscal_regularization_id"] = reg.id
        if not self._valid_period_code(
            getattr(move, "justech_do_original_fiscal_period", False)
        ):
            move_vals["justech_do_original_fiscal_period"] = period
        if not self._valid_period_code(
            getattr(move, "justech_do_608_reporting_period", False)
        ):
            move_vals["justech_do_608_reporting_period"] = period
        if (
            hasattr(move, "justech_do_fiscal_regularization_state")
            and not move.justech_do_fiscal_regularization_state
        ):
            move_vals["justech_do_fiscal_regularization_state"] = "pending_regularization"
        if (
            hasattr(move, "justech_do_regularization_responsible_id")
            and not move.justech_do_regularization_responsible_id
            and responsible
        ):
            move_vals["justech_do_regularization_responsible_id"] = responsible.id
        if move_vals:
            move.write(move_vals)

        self._ensure_activity(reg)
        return reg

    def ensure_regularization_for_move(
        self,
        move,
        *,
        reason=None,
        cancel_type=None,
        source_operation="direct_cancel",
        cancelled_by=None,
        linked_moves=None,
    ):
        """Crea/actualiza línea de regularización + actividad (sin duplicar)."""
        move.ensure_one()
        ncf = move._justech_get_issued_ncf() if hasattr(move, "_justech_get_issued_ncf") else (
            move.justech_do_ncf or False
        )
        if not ncf and not move.justech_do_ncf_voided:
            # Sin NCF no hay línea 608
            return self.env["justech.do.fiscal.regularization"]

        resolved = self.resolve_original_period(move)
        period = resolved["original_fiscal_period"]
        was_in_607 = resolved["was_in_607"]
        review = resolved["review_required"]

        status_608 = "pending"
        if period and self._608_already_presented(move.company_id, period):
            status_608 = "rectification_required"

        it1 = self._evaluate_it1_impact(move)
        responsible = (
            move.company_id.justech_do_fiscal_regularization_user_id
            or move.justech_do_regularization_responsible_id
            or cancelled_by
            or self.env.user
        )

        Reg = self.env["justech.do.fiscal.regularization"]
        existing = Reg.search(
            [
                ("company_id", "=", move.company_id.id),
                ("move_id", "=", move.id),
                ("ncf", "=", ncf or False),
                ("original_fiscal_period", "=", period or False),
            ],
            limit=1,
        )
        vals = {
            "company_id": move.company_id.id,
            "move_id": move.id,
            "ncf": ncf or False,
            "document_type": move.move_type,
            "partner_id": move.partner_id.id,
            "invoice_date": resolved["invoice_date"],
            "original_invoice_date": resolved["invoice_date"],
            "original_fiscal_period": period or False,
            "cancellation_execution_date": fields.Datetime.now(),
            "reporting_period_608": period or False,
            "annulment_type_608": cancel_type
            or move.justech_do_ncf_cancel_type
            or False,
            "required_608": True,
            "status_608": status_608,
            "rectification_607_required": bool(was_in_607 and period),
            "rectification_607_period": period if was_in_607 else False,
            "status_607": "pending" if was_in_607 else "na",
            "rectification_it1_required": bool(it1 and period),
            "rectification_it1_period": period if it1 else False,
            "status_it1": "validation_required" if it1 else "na",
            "responsible_user_id": responsible.id if responsible else False,
            "cancellation_reason": reason or move.justech_do_direct_cancel_reason,
            "source_operation": source_operation,
            "cancelled_by_user_id": (cancelled_by or self.env.user).id,
            "general_status": "review_required" if review else "pending",
            "amount_total": move.amount_total,
            "deadline": fields.Date.context_today(move) + timedelta(days=15),
        }

        # Campos mirror en el move (fuente para 608 exporter)
        move_vals = {
            "justech_do_original_fiscal_period": period or False,
            "justech_do_608_reporting_period": period or False,
            "justech_do_cancellation_execution_date": fields.Datetime.now(),
            "justech_do_regularization_responsible_id": responsible.id
            if responsible
            else False,
            "justech_do_fiscal_regularization_state": "pending_regularization",
        }
        if was_in_607:
            move_vals["justech_do_included_in_607"] = True
            move_vals["justech_do_fiscal_treatment_planned"] = "rectify_607"
        else:
            move_vals["justech_do_fiscal_treatment_planned"] = "format_608"
        move.write(move_vals)

        if existing:
            # No pisar estados avanzados 608/607 ya presentados
            safe = {
                k: v
                for k, v in vals.items()
                if k
                not in (
                    "status_608",
                    "status_607",
                    "status_it1",
                    "general_status",
                    "activity_id",
                )
            }
            if existing.status_608 in ("pending", "rectification_required"):
                safe["status_608"] = status_608
            existing.write(safe)
            reg = existing
        else:
            reg = Reg.create(vals)

        if linked_moves:
            linked_regs = Reg.search([("move_id", "in", linked_moves.ids)])
            if linked_regs:
                reg.write(
                    {
                        "linked_regularization_ids": [
                            (4, r.id) for r in linked_regs if r.id != reg.id
                        ]
                    }
                )

        self._ensure_activity(reg)
        return reg

    def _activity_summary(self, reg):
        label = self.format_period_label(reg.original_fiscal_period)
        if reg.rectification_607_required and reg.rectification_it1_required:
            return _(
                "Rectificar 607 e IT-1 e incluir NCF en 608 de %(p)s"
            ) % {"p": label}
        if reg.rectification_607_required:
            return _("Rectificar 607 e incluir NCF en 608 de %(p)s") % {"p": label}
        if reg.general_status == "review_required":
            return _("Validar período fiscal e incluir NCF anulado en 608")
        return _("Incluir NCF anulado en 608 de %(p)s") % {"p": label}

    def _activity_note(self, reg):
        label = self.format_period_label(reg.original_fiscal_period)
        exec_dt = reg.cancellation_execution_date or fields.Datetime.now()
        linked = ", ".join(
            "%s (%s)" % (r.move_id.name, r.ncf or "—")
            for r in reg.linked_regularization_ids
        ) or _("Ninguna")
        lines = [
            _(
                "La factura %(doc)s, NCF %(ncf)s, correspondiente al período %(p)s, "
                "fue cancelada internamente el %(exec)s."
            )
            % {
                "doc": reg.move_id.name,
                "ncf": reg.ncf or "—",
                "p": label,
                "exec": fields.Datetime.to_string(exec_dt),
            },
            "",
            _("Acciones requeridas:"),
            _("1. Incluir el NCF en el Formato 608 de %(p)s.") % {"p": label},
            _("2. Rectificar el Formato 607 de %(p)s, si fue reportado.") % {"p": label},
            _(
                "3. Validar y rectificar el IT-1 de %(p)s, cuando corresponda."
            )
            % {"p": label},
            _("4. Revisar documentos vinculados: %(l)s.") % {"l": linked},
            _("5. Presentar los archivos corregidos ante la DGII."),
            _("6. Adjuntar constancia, acuse o evidencia."),
            _("7. Marcar la regularización como completada."),
            "",
            _("Empresa: %(c)s") % {"c": reg.company_id.display_name},
            _("Cliente: %(p)s") % {"p": reg.partner_id.display_name or "—"},
            _("Motivo 608: %(t)s") % {"t": reg.annulment_type_608 or "—"},
            _("Motivo: %(r)s") % {"r": reg.cancellation_reason or "—"},
            _("Cancelado por: %(u)s")
            % {"u": (reg.cancelled_by_user_id or self.env.user).display_name},
            _("Total: %(a)s") % {"a": reg.amount_total},
        ]
        if reg.status_608 == "rectification_required":
            lines.insert(
                3,
                _(
                    "ATENCIÓN: el 608 de %(p)s ya fue presentado — se requiere "
                    "rectificativa completa del período."
                )
                % {"p": label},
            )
        return "\n".join(lines)

    def _ensure_activity(self, reg):
        """Una actividad abierta por company+NCF+período+tipo."""
        reg.ensure_one()
        if not reg.responsible_user_id:
            return False
        Activity = self.env["mail.activity"]
        domain = [
            ("res_model", "=", "justech.do.fiscal.regularization"),
            ("res_id", "=", reg.id),
            ("activity_type_id", "=", self.env.ref("mail.mail_activity_data_todo").id),
        ]
        existing = Activity.search(domain, limit=1)
        summary = self._activity_summary(reg)
        note = self._activity_note(reg)
        vals = {
            "summary": summary,
            "note": note,
            "user_id": reg.responsible_user_id.id,
            "date_deadline": reg.deadline or fields.Date.context_today(reg),
        }
        if existing:
            existing.write(vals)
            reg.activity_id = existing.id
            return existing
        # También evitar duplicados por NCF+período en el move
        move_acts = Activity.search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", reg.move_id.id),
                ("summary", "ilike", "608"),
                ("user_id", "=", reg.responsible_user_id.id),
            ],
            limit=5,
        )
        for act in move_acts:
            if reg.original_fiscal_period and reg.original_fiscal_period in (
                act.summary or ""
            ):
                act.write(vals)
                reg.activity_id = act.id
                return act

        act = reg.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=reg.responsible_user_id.id,
            summary=summary,
            note=note,
            date_deadline=reg.deadline or fields.Date.context_today(reg),
        )
        act_rec = Activity.search(domain, limit=1)
        if act_rec:
            reg.activity_id = act_rec.id
        return act_rec
