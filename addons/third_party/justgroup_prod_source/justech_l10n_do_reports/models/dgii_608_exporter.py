"""Exportador DGII 608 — comprobantes fiscales anulados.

Período = período fiscal original del comprobante (608_reporting_period /
original_fiscal_period / invoice_date), NO la fecha de ejecución de cancelación.
"""
from __future__ import annotations

import re
from datetime import date

from odoo import _, fields, models

NCF_FULL_RE = re.compile(r"^[BE][0-9]{2}[0-9]{8}$")


class JustechDoDgii608Exporter(models.AbstractModel):
    _name = "justech.do.dgii.608.exporter"
    _inherit = "justech.do.dgii.exporter.mixin"
    _description = "Exportador DGII formato 608"

    def _dgii_report_code(self):
        return "608"

    def _dgii_mapping_filename(self):
        return "dgii_608_mapping.json"

    def _dgii_summary_title(self):
        return _("Resumen validación 608")

    def _dgii_partner_role_label(self):
        return _("Contacto")

    def _dgii_text_columns(self):
        return {"A", "C"}

    def _dgii_withholding_affects(self, catalog):
        return False

    def _is_cancelled_move(self, move):
        # En 608 los anulados SÍ van al reporte; no marcar como «cancelled» bucket.
        return False

    def _is_excluded_from_report(self, move):
        # Anulados pertenecen al 608 aunque justech_do_include_in_dgii=False (607).
        return bool((move.justech_do_dgii_exclusion_reason or "").strip())

    def _period_code_from_date(self, day):
        day = fields.Date.to_date(day)
        if not day:
            return False
        return day.strftime("%Y%m")

    def _608_reporting_period(self, move):
        """Fuente: 608_reporting_period → original_fiscal_period → invoice_date.

        Nunca write_date / create_date / fecha de button_cancel.
        """
        for fname in (
            "justech_do_608_reporting_period",
            "justech_do_original_fiscal_period",
        ):
            if fname in move._fields:
                code = (move[fname] or "").strip()
                if len(code) == 6 and code.isdigit():
                    return code
        if "justech.do.fiscal.regularization" in self.env:
            Reg = self.env["justech.do.fiscal.regularization"].sudo()
            reg = Reg.search(
                [("move_id", "=", move.id), ("required_608", "=", True)],
                order="id desc",
                limit=1,
            )
            if reg and reg.reporting_period_608:
                return reg.reporting_period_608
        inv = move.invoice_date or move.date
        return self._period_code_from_date(inv)

    def _period_bounds(self, date_from, date_to):
        return (
            self._period_code_from_date(date_from),
            self._period_code_from_date(date_to),
        )

    def _move_in_608_period(self, move, date_from, date_to):
        period = self._608_reporting_period(move)
        if not period:
            return False
        p_from, p_to = self._period_bounds(date_from, date_to)
        if p_from and p_to and p_from == p_to:
            return period == p_from
        # Rango multi-mes: el día 1 del período debe caer en [date_from, date_to]
        if len(period) == 6 and period.isdigit():
            try:
                day = date(int(period[:4]), int(period[4:6]), 1)
            except ValueError:
                return False
            return date_from <= day <= date_to
        return False

    def _dgii_base_period_domain(self, company, date_from, date_to):
        # Incluir cancelados (cancelación directa) y posted voided.
        domain = [
            ("company_id", "=", company.id),
            ("state", "in", ("posted", "cancel")),
        ]
        Move = self.env["account.move"]
        if "justech_do_ncf_voided" in Move._fields and "l10n_do_cancellation_type" in Move._fields:
            domain.extend(
                [
                    "|",
                    ("justech_do_ncf_voided", "=", True),
                    ("l10n_do_cancellation_type", "!=", False),
                ]
            )
        elif "justech_do_ncf_voided" in Move._fields:
            domain.append(("justech_do_ncf_voided", "=", True))
        elif "l10n_do_cancellation_type" in Move._fields:
            domain.append(("l10n_do_cancellation_type", "!=", False))
        return domain

    def classify_moves(self, company, date_from, date_to, refresh_states=True):
        all_moves = self.env["account.move"].search(
            self._dgii_base_period_domain(company, date_from, date_to),
            order="invoice_date, id",
        )
        fdp = self._fdp()
        period_moves = all_moves.filtered(
            lambda m: fdp.is_voided(m) and self._move_in_608_period(m, date_from, date_to)
        )
        buckets = {
            "all": period_moves,
            "cancelled": self.env["account.move"],
            "excluded": self.env["account.move"],
            "incomplete": self.env["account.move"],
            "valid": self.env["account.move"],
        }
        for move in period_moves:
            if refresh_states:
                state = self._refresh_move_fiscal_state(move, date_from, date_to)
            elif self._is_excluded_from_report(move):
                state = "excluded"
            elif self._dgii_validate_single_move(move, date_from, date_to):
                state = "incomplete"
            else:
                state = "valid"
            buckets[state] |= move
        return buckets

    def _ncf_is_valid_format(self, ncf):
        ncf = (ncf or "").strip().upper().replace(" ", "")
        return bool(NCF_FULL_RE.match(ncf))

    def _cancel_type_code(self, move):
        return self._fdp().get_cancellation_type(move)

    def _ncf_prefix(self, move):
        return self._fdp().get_document_type_prefix(move)

    def _void_user_name(self, move):
        consumption = self.env["justech.do.ncf.consumption"].search(
            [("move_id", "=", move.id), ("state", "=", "voided")],
            limit=1,
        )
        if consumption and consumption.void_user_id:
            return consumption.void_user_id.display_name
        return ""

    def _refresh_move_fiscal_state(self, move, date_from, date_to):
        if self._is_excluded_from_report(move):
            state = "excluded"
        elif self._dgii_validate_single_move(move, date_from, date_to):
            state = "incomplete"
        else:
            state = "valid"
        if move.justech_do_dgii_fiscal_state != state:
            # Conservar cancelled en el move; usar valid/incomplete solo en buckets.
            if move.justech_do_dgii_fiscal_state != "cancelled":
                move.justech_do_dgii_fiscal_state = state
        return state

    def _dgii_validate_single_move(self, move, date_from, date_to):
        errors = []
        label = self._move_label(move)
        fdp = self._fdp()
        if not fdp.is_voided(move):
            errors.append(_("%(doc)s: el comprobante no está anulado.") % {"doc": label})
        ncf = fdp.get_ncf(move)
        if not ncf:
            errors.append(_("%(doc)s: falta NCF anulado.") % {"doc": label})
        elif not self._ncf_is_valid_format(ncf):
            errors.append(
                _("%(doc)s: NCF inválido «%(ncf)s».")
                % {"doc": label, "ncf": ncf}
            )
        period = self._608_reporting_period(move)
        if not period:
            errors.append(
                _(
                    "%(doc)s: no se pudo determinar el período fiscal original "
                    "para el 608."
                )
                % {"doc": label}
            )
        elif not self._move_in_608_period(move, date_from, date_to):
            errors.append(
                _(
                    "%(doc)s: el período 608 %(period)s no corresponde al "
                    "período seleccionado (no usar fecha de cancelación)."
                )
                % {"doc": label, "period": period}
            )
        if not self._cancel_type_code(move):
            errors.append(_("%(doc)s: falta tipo de anulación DGII (608).") % {"doc": label})
        if not fdp.get_void_reason(move) and not fdp.get_cancellation_type(move):
            errors.append(_("%(doc)s: falta motivo de anulación.") % {"doc": label})
        return errors

    def format_validation_summary(self, result):
        lines = super().format_validation_summary(result).split("\n")
        counts = result["counts"]
        lines.extend(
            [
                "",
                _("Resumen de anulados (documentos válidos)"),
                "—" * 24,
                _("Comprobantes exportables: %(n)s") % {"n": counts["valid"]},
                _("Documentos excluidos: %(n)s") % {"n": counts["excluded"]},
                _("Documentos incompletos: %(n)s") % {"n": counts["incomplete"]},
                _(
                    "Filtro de período: período fiscal original "
                    "(608_reporting_period), no fecha de cancelación."
                ),
            ]
        )
        return "\n".join(lines)

    def _dgii_build_row_values(self, move, line_number, date_from, date_to):
        fdp = self._fdp()
        return {
            "A": fdp.get_ncf(move),
            "B": self._format_dgii_date(move.invoice_date),
            "C": self._cancel_type_code(move),
        }

    def _moves_for_period(self, company, date_from, date_to, only_valid=True):
        buckets = self.classify_moves(company, date_from, date_to)
        if only_valid:
            return buckets["valid"]
        return buckets["all"].filtered(lambda m: not self._is_excluded_from_report(m))

    def validate_period_608(self, company, date_from, date_to, refresh_states=True):
        return self.validate_period(company, date_from, date_to, refresh_states)
