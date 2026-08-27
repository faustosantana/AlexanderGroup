# -*- coding: utf-8 -*-
"""Utilidades de período fiscal DGII (YYYYMM) y selección mes/rango."""
from __future__ import annotations

import calendar
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_PERIOD_RE = re.compile(r"^\d{6}$")

MONTH_SELECTION = [
    ("1", "Enero"),
    ("2", "Febrero"),
    ("3", "Marzo"),
    ("4", "Abril"),
    ("5", "Mayo"),
    ("6", "Junio"),
    ("7", "Julio"),
    ("8", "Agosto"),
    ("9", "Septiembre"),
    ("10", "Octubre"),
    ("11", "Noviembre"),
    ("12", "Diciembre"),
]


class JustechDoDgiiPeriod(models.AbstractModel):
    _name = "justech.do.dgii.period"
    _description = "Utilidades período fiscal DGII"

    @api.model
    def default_period_code(self, reference_date=None):
        ref = reference_date or fields.Date.context_today(self)
        ref = fields.Date.to_date(ref)
        return ref.strftime("%Y%m")

    @api.model
    def period_bounds_from_code(self, period_code):
        """Convierte YYYYMM en (primer día, último día) del mes."""
        code = (period_code or "").strip()
        if not _PERIOD_RE.match(code):
            raise UserError(
                _("Período inválido «%(p)s». Use formato YYYYMM, por ejemplo 202606.")
                % {"p": period_code or ""}
            )
        year = int(code[:4])
        month = int(code[4:6])
        if month < 1 or month > 12:
            raise UserError(
                _("Mes inválido en período %(p)s. Debe estar entre 01 y 12.")
                % {"p": code}
            )
        if year < 2000 or year > 2100:
            raise UserError(
                _("Año inválido en período %(p)s.") % {"p": code}
            )
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    @api.model
    def period_code_from_year_month(self, year, month):
        year = int(year)
        month = int(month)
        if month < 1 or month > 12:
            raise UserError(_("Mes inválido. Debe estar entre 1 y 12."))
        if year < 2000 or year > 2100:
            raise UserError(_("Año inválido."))
        return f"{year:04d}{month:02d}"

    @api.model
    def period_code_from_dates(self, date_from, date_to):
        """Deriva YYYYMM desde la fecha inicial del período."""
        date_from = fields.Date.to_date(date_from)
        if not date_from:
            return False
        return date_from.strftime("%Y%m")

    @api.model
    def validate_period_dates(self, date_from, date_to, period_code=None):
        """Valida coherencia entre fechas y período YYYYMM."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if not date_from or not date_to:
            raise UserError(_("Debe indicar fecha desde y fecha hasta."))
        if date_from > date_to:
            raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))
        if period_code:
            expected_from, expected_to = self.period_bounds_from_code(period_code)
            if date_from != expected_from or date_to != expected_to:
                raise UserError(
                    _(
                        "Las fechas %(desde)s — %(hasta)s no coinciden con el período %(periodo)s "
                        "(esperado: %(exp_desde)s — %(exp_hasta)s)."
                    )
                    % {
                        "desde": date_from,
                        "hasta": date_to,
                        "periodo": period_code,
                        "exp_desde": expected_from,
                        "exp_hasta": expected_to,
                    }
                )
        return date_from, date_to

    @api.model
    def validate_custom_range(self, date_from, date_to):
        """Valida rango personalizado (auditoría); no exige mes completo."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if not date_from or not date_to:
            raise UserError(_("Debe indicar fecha desde y fecha hasta."))
        if date_from > date_to:
            raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))
        return date_from, date_to


class JustechDoDgiiPeriodSelectorMixin(models.AbstractModel):
    """Mixin reutilizable: Mes fiscal vs Rango personalizado.

    El modelo concreto debe declarar ``period_code``, ``date_from`` y ``date_to``.
    """

    _name = "justech.do.dgii.period.selector.mixin"
    _description = "Selector de período DGII (mes / rango)"

    period_mode = fields.Selection(
        [
            ("month", "Mes fiscal"),
            ("custom", "Rango personalizado"),
        ],
        string="Tipo de período",
        default="month",
        required=True,
    )
    period_year = fields.Integer(
        string="Año",
        default=lambda self: fields.Date.context_today(self).year,
    )
    period_month = fields.Selection(
        selection=MONTH_SELECTION,
        string="Mes",
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    period_official_hint = fields.Char(
        string="Aviso DGII",
        compute="_compute_period_official_hint",
    )

    @api.depends("period_mode")
    def _compute_period_official_hint(self):
        for rec in self:
            if rec.period_mode == "custom":
                rec.period_official_hint = (
                    "Los archivos oficiales DGII normalmente se generan por período "
                    "fiscal mensual. Este rango sirve para auditoría, revisión y análisis; "
                    "no asuma que un rango parcial puede enviarse como declaración oficial."
                )
            else:
                rec.period_official_hint = False

    def _justech_apply_month_period(self):
        self.ensure_one()
        period_util = self.env["justech.do.dgii.period"]
        code = period_util.period_code_from_year_month(
            self.period_year, int(self.period_month)
        )
        date_from, date_to = period_util.period_bounds_from_code(code)
        self.period_code = code
        self.date_from = date_from
        self.date_to = date_to

    @api.onchange("period_mode", "period_year", "period_month")
    def _onchange_justech_period_selector(self):
        if self.period_mode == "month" and self.period_year and self.period_month:
            try:
                self._justech_apply_month_period()
                if "validation_state" in self._fields:
                    self.validation_state = "pending"
                    self.validation_log = False
            except UserError as err:
                return {"warning": {"title": _("Período inválido"), "message": str(err)}}
        return None

    @api.onchange("date_from", "date_to")
    def _onchange_justech_custom_dates(self):
        if getattr(self, "period_mode", "month") != "custom":
            return None
        if self.date_from and self.date_to and self.date_from > self.date_to:
            return {
                "warning": {
                    "title": _("Fechas incoherentes"),
                    "message": _("La fecha desde no puede ser posterior a la fecha hasta."),
                }
            }
        if self.date_from and "period_code" in self._fields:
            self.period_code = self.env["justech.do.dgii.period"].period_code_from_dates(
                self.date_from, self.date_to
            )
        if "validation_state" in self._fields:
            self.validation_state = "pending"
            self.validation_log = False
        return None

    @api.model
    def _justech_normalize_period_vals(self, vals, record=None):
        """Normaliza vals de create/write según period_mode."""
        period_util = self.env["justech.do.dgii.period"]
        mode = vals.get("period_mode")
        if mode is None and record:
            mode = record.period_mode
        mode = mode or "month"
        vals = dict(vals)
        if mode == "month":
            year = vals.get("period_year")
            month = vals.get("period_month")
            if year is None and record:
                year = record.period_year
            if month is None and record:
                month = record.period_month
            if not year or not month:
                # fallback from period_code
                code = vals.get("period_code") or (record.period_code if record else None)
                if code:
                    date_from, date_to = period_util.period_bounds_from_code(code)
                    vals.setdefault("date_from", date_from)
                    vals.setdefault("date_to", date_to)
                    vals.setdefault("period_code", code)
                    vals.setdefault("period_year", int(code[:4]))
                    vals.setdefault("period_month", str(int(code[4:6])))
                return vals
            # Selection keys are "1".."12" (sin cero a la izquierda).
            month = str(int(month))
            vals["period_month"] = month
            code = period_util.period_code_from_year_month(year, int(month))
            date_from, date_to = period_util.period_bounds_from_code(code)
            vals["period_code"] = code
            vals["date_from"] = date_from
            vals["date_to"] = date_to
        elif mode == "custom":
            date_from = vals.get("date_from")
            date_to = vals.get("date_to")
            if date_from is None and record:
                date_from = record.date_from
            if date_to is None and record:
                date_to = record.date_to
            if date_from and date_to:
                period_util.validate_custom_range(date_from, date_to)
                vals["period_code"] = period_util.period_code_from_dates(
                    date_from, date_to
                )
        return vals
