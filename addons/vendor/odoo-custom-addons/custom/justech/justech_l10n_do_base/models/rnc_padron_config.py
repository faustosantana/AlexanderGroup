# -*- coding: utf-8 -*-
"""Configuración de padrón RNC / actualización automática."""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

DEFAULT_DGII_URL = (
    "https://dgii.gov.do/app/WebApps/Consultas/rnc/DGII_RNC.zip"
)
ALLOWED_DGII_HOSTS = ("dgii.gov.do", "www.dgii.gov.do")


class JustechDoRncPadronConfig(models.Model):
    _name = "justech.do.rnc.padron.config"
    _description = "Configuración padrón RNC DGII"
    _rec_name = "display_name"

    display_name = fields.Char(default="Configuración padrón DGII", readonly=True)
    auto_update_enabled = fields.Boolean(
        string="Actualización automática",
        default=False,
    )
    frequency_days = fields.Integer(
        string="Frecuencia (días)",
        default=45,
        required=True,
    )
    max_age_days = fields.Integer(
        string="Antigüedad máxima permitida (días)",
        default=90,
        required=True,
        help="Usado por el Health Check para marcar padrón desactualizado.",
    )
    official_url = fields.Char(
        string="URL oficial DGII",
        default=DEFAULT_DGII_URL,
        required=True,
    )
    run_hour = fields.Integer(
        string="Hora de ejecución (0-23)",
        default=3,
        required=True,
    )
    min_keep_ratio = fields.Float(
        string="Ratio mínimo vs padrón vigente",
        default=0.90,
        required=True,
        help="Si el archivo nuevo tiene menos de este porcentaje de registros, se aborta.",
    )
    max_error_ratio = fields.Float(
        string="Ratio máximo de filas rechazadas",
        default=0.05,
        required=True,
    )
    max_retries = fields.Integer(string="Reintentos máximos", default=3, required=True)
    retry_hours = fields.Integer(
        string="Horas entre reintentos",
        default=4,
        required=True,
    )
    last_run_at = fields.Datetime(string="Última ejecución", readonly=True)
    next_run_at = fields.Datetime(string="Próxima ejecución", readonly=True)
    last_success_at = fields.Datetime(string="Última ejecución exitosa", readonly=True)
    last_status = fields.Selection(
        [
            ("never", "Nunca ejecutado"),
            ("updated", "Actualizado"),
            ("unchanged", "Sin cambios"),
            ("available", "Actualización disponible"),
            ("running", "En proceso"),
            ("failed", "Fallido"),
            ("source_unavailable", "Fuente no disponible"),
            ("review_required", "Revisión requerida"),
        ],
        string="Estado última ejecución",
        default="never",
        readonly=True,
    )
    last_message = fields.Text(string="Mensaje última ejecución", readonly=True)
    retry_count = fields.Integer(string="Reintentos actuales", default=0, readonly=True)
    notify_admins = fields.Boolean(
        string="Notificar a administradores",
        default=True,
    )
    lock_until = fields.Datetime(string="Bloqueo hasta", readonly=True)
    cron_active = fields.Boolean(
        string="Cron activo",
        compute="_compute_cron_active",
        help="Refleja el estado del ir.cron de actualización automática.",
    )

    @api.depends("auto_update_enabled")
    def _compute_cron_active(self):
        for rec in self:
            rec.cron_active = rec._cron_is_active()

    def _cron_record(self):
        return self.env.ref(
            "justech_l10n_do_base.ir_cron_justech_rnc_padron_auto_update",
            raise_if_not_found=False,
        )

    def _cron_is_active(self):
        cron = self._cron_record()
        return bool(cron and cron.active)

    def _sync_ir_cron(self):
        """Sincroniza ir.cron.active con auto_update_enabled."""
        self.ensure_one()
        cron = self._cron_record()
        if cron and cron.active != bool(self.auto_update_enabled):
            cron.sudo().write({"active": bool(self.auto_update_enabled)})

    def _next_run_datetime(self, from_dt=None):
        """Próxima ejecución: frequency_days + run_hour (UTC naive Odoo)."""
        self.ensure_one()
        base = fields.Datetime.to_datetime(from_dt or fields.Datetime.now())
        days = self.frequency_days or 45
        hour = self.run_hour if self.run_hour is not None else 3
        target = base + timedelta(days=days)
        target = target.replace(hour=int(hour), minute=0, second=0, microsecond=0)
        if target <= fields.Datetime.now():
            target = fields.Datetime.now() + timedelta(days=days)
            target = target.replace(hour=int(hour), minute=0, second=0, microsecond=0)
        return target

    @api.constrains("frequency_days", "max_age_days", "run_hour", "min_keep_ratio")
    def _check_config_values(self):
        for rec in self:
            if rec.frequency_days < 1:
                raise ValidationError(_("La frecuencia debe ser al menos 1 día."))
            if rec.max_age_days < 1:
                raise ValidationError(_("La antigüedad máxima debe ser al menos 1 día."))
            if not (0 <= rec.run_hour <= 23):
                raise ValidationError(_("La hora de ejecución debe estar entre 0 y 23."))
            if not (0.5 <= rec.min_keep_ratio <= 1.0):
                raise ValidationError(
                    _("El ratio mínimo debe estar entre 0.50 y 1.00.")
                )

    @api.constrains("official_url")
    def _check_official_url(self):
        for rec in self:
            rec._validate_official_url(rec.official_url)

    @api.model
    def _validate_official_url(self, url):
        parsed = urlparse(url or "")
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValidationError(_("URL oficial inválida."))
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_DGII_HOSTS:
            raise ValidationError(
                _(
                    "La URL debe pertenecer al dominio oficial de la DGII "
                    "(%(hosts)s)."
                )
                % {"hosts": ", ".join(ALLOWED_DGII_HOSTS)}
            )
        return True

    @api.model
    def get_config(self):
        """Obtiene o crea el singleton de configuración (lectura segura)."""
        Config = self.sudo()
        existing = Config.search([], limit=1, order="id")
        if existing:
            return existing
        return Config.create(
            {
                "official_url": DEFAULT_DGII_URL,
                "auto_update_enabled": False,
                "frequency_days": 45,
                "max_age_days": 90,
            }
        )

    def action_save_and_schedule(self):
        self.ensure_one()
        self._validate_official_url(self.official_url)
        if self.auto_update_enabled:
            self.next_run_at = self._next_run_datetime()
        else:
            self.next_run_at = False
        self._sync_ir_cron()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuración guardada"),
                "message": _(
                    "Actualización automática %(state)s. Frecuencia: %(days)s días. "
                    "Hora: %(hour)s:00. Cron: %(cron)s."
                )
                % {
                    "state": _("activa") if self.auto_update_enabled else _("inactiva"),
                    "days": self.frequency_days or 45,
                    "hour": self.run_hour if self.run_hour is not None else 3,
                    "cron": _("activo") if self._cron_is_active() else _("inactivo"),
                },
                "type": "success",
            },
        }

    def action_run_now(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(_("Solo Administradores Fiscales pueden ejecutar esto."))
        return self.env["justech.do.rnc.padron.auto.service"].run_auto_update(
            force=True
        )
