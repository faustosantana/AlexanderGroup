# -*- coding: utf-8 -*-
"""Actualización automática del padrón RNC desde DGII."""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ALLOWED_HOSTS = ("dgii.gov.do", "www.dgii.gov.do")
DEFAULT_URL = "https://dgii.gov.do/app/WebApps/Consultas/rnc/DGII_RNC.zip"
UA = (
    "Mozilla/5.0 (compatible; JustechPadronBot/1.0; +https://justech.do)"
)


class JustechDoRncPadronAutoService(models.AbstractModel):
    _name = "justech.do.rnc.padron.auto.service"
    _description = "Servicio actualización automática padrón RNC"

    @api.model
    def _notify_admins(self, title, body, notif_type="warning"):
        config = self.env["justech.do.rnc.padron.config"].sudo().get_config()
        if not config.notify_admins:
            return
        _logger.warning("PADRON_ADMIN_NOTIFY [%s] %s — %s", notif_type, title, body)
        try:
            # Odoo 19: res.groups.user_ids
            users = self.env.ref("base.group_system").sudo().user_ids
            for user in users:
                partner = user.partner_id
                if not partner:
                    continue
                self.env["bus.bus"]._sendone(
                    partner,
                    "simple_notification",
                    {
                        "title": title,
                        "message": body,
                        "type": notif_type if notif_type != "danger" else "danger",
                        "sticky": notif_type in ("danger", "warning"),
                    },
                )
        except Exception:  # noqa: BLE001
            _logger.exception("No se pudo enviar notificación de padrón")

    @api.model
    def download_official(self, url=None):
        config = self.env["justech.do.rnc.padron.config"].get_config()
        url = url or config.official_url or DEFAULT_URL
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise UserError(
                _("Fuente no permitida. Solo dominio oficial DGII: %s")
                % ", ".join(ALLOWED_HOSTS)
            )
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        # Descarga con reintentos de rango si el servidor corta
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                code = getattr(resp, "status", 200)
                if code >= 400:
                    raise UserError(_("HTTP %(code)s al descargar padrón.") % {"code": code})
                ctype = (resp.headers.get("Content-Type") or "").lower()
                data = resp.read()
        except urllib.error.HTTPError as e:
            raise UserError(_("Error HTTP DGII: %s") % e.code) from e
        except urllib.error.URLError as e:
            raise UserError(_("No se pudo contactar la DGII: %s") % e.reason) from e

        if not data or len(data) < 1000:
            raise UserError(_("Archivo descargado vacío o demasiado pequeño."))
        # Si truncado típico 16MB, reintentar por rangos
        cl = None
        try:
            head_req = urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": UA}
            )
            with urllib.request.urlopen(head_req, timeout=60) as h:
                cl = h.headers.get("Content-Length")
        except Exception:  # noqa: BLE001
            cl = None
        if cl and int(cl) > len(data):
            data = self._download_by_ranges(url, int(cl))
        filename = "DGII_RNC.zip"
        if "txt" in (ctype or "") or url.lower().endswith(".txt"):
            filename = "DGII_RNC.TXT"
        return data, filename

    @api.model
    def _download_by_ranges(self, url, total):
        chunk = 4 * 1024 * 1024
        parts = []
        offset = 0
        while offset < total:
            end = min(offset + chunk - 1, total - 1)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Range": f"bytes={offset}-{end}",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                parts.append(resp.read())
            offset = end + 1
            time.sleep(0.2)
        return b"".join(parts)

    @api.model
    def run_auto_update(self, force=False):
        """Cron / botón Actualizar ahora.

        Para UAT controlado (sin URL real):
        with_context(
            justech_padron_test_payload=bytes,
            justech_padron_test_filename='fixture.txt',
            justech_padron_allow_test_fixture=True,
        )
        """
        ImportSvc = self.env["justech.do.rnc.padron.import.service"]
        config = self.env["justech.do.rnc.padron.config"].sudo().get_config()
        if not force and not config.auto_update_enabled:
            return True
        now = fields.Datetime.now()
        if not force and config.next_run_at and config.next_run_at > now:
            return True
        # Ventana horaria: el cron diario solo ejecuta en run_hour (salvo force).
        if not force and config.run_hour is not None and now.hour != int(config.run_hour):
            return True

        try:
            test_payload = self.env.context.get("justech_padron_test_payload")
            if test_payload is not None:
                raw = test_payload
                filename = self.env.context.get(
                    "justech_padron_test_filename", "padron_fixture.txt"
                )
                import_ctx = {
                    "justech_padron_allow_test_fixture": True,
                }
                if self.env.context.get("justech_padron_full_source"):
                    import_ctx["justech_padron_full_source"] = True
                if self.env.context.get("justech_padron_skip_ratio_check"):
                    import_ctx["justech_padron_skip_ratio_check"] = True
                log = ImportSvc.with_context(**import_ctx).apply_import(
                    raw,
                    filename,
                    source="auto" if not force else "update",
                    delimiter="|",
                    has_header=False,
                )
            else:
                raw, filename = self.download_official()
                log = ImportSvc.with_context(justech_padron_full_source=True).apply_import(
                    raw,
                    filename,
                    source="auto" if not force else "update",
                    delimiter="|",
                    has_header=False,
                )
            if log.state == "failed":
                self._handle_failure(config, log.error_message or _("Fallo desconocido"))
            else:
                config.with_context(justech_padron_log_allow_write=True).sudo().write(
                    {
                        "retry_count": 0,
                        "last_run_at": fields.Datetime.now(),
                        "last_success_at": fields.Datetime.now(),
                        "last_status": "unchanged"
                        if "idéntico" in (log.summary or "").lower()
                        or "sin cambios" in (log.summary or "").lower()
                        else "updated",
                        "last_message": log.summary or "",
                        "next_run_at": config._next_run_datetime()
                        if config.auto_update_enabled
                        else False,
                    }
                )
                if config.notify_admins and log.state in ("done", "done_warn"):
                    self._notify_admins(
                        _("Padrón DGII actualizado"),
                        log.summary or "",
                        "success",
                    )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Actualización padrón"),
                    "message": log.summary or log.error_message or _("Proceso finalizado."),
                    "type": "success" if log.state != "failed" else "danger",
                    "sticky": log.state == "failed",
                },
            }
        except Exception as exc:
            self._handle_failure(config, str(exc))
            if force:
                raise
            return True

    @api.model
    def _handle_failure(self, config, message):
        retries = (config.retry_count or 0) + 1
        max_retries = config.max_retries or 3
        vals = {
            "last_run_at": fields.Datetime.now(),
            "last_status": "failed"
            if retries >= max_retries
            else "source_unavailable",
            "last_message": message,
            "retry_count": retries,
            "lock_until": False,
        }
        if retries < max_retries:
            vals["next_run_at"] = fields.Datetime.now() + timedelta(
                hours=config.retry_hours or 4
            )
        else:
            vals["next_run_at"] = (
                config._next_run_datetime()
                if config.auto_update_enabled
                else False
            )
            self._notify_admins(
                _("Fallo actualización padrón DGII"),
                _(
                    "Se agotaron %(n)s reintentos. El padrón vigente se conserva.\n%(m)s"
                )
                % {"n": max_retries, "m": message},
                "danger",
            )
        config.with_context(justech_padron_log_allow_write=True).sudo().write(vals)

    @api.model
    def cron_auto_update(self):
        """Método invocado por ir.cron (sudo)."""
        return self.sudo().run_auto_update(force=False)

    @api.model
    def retry_last_failed(self):
        """Reintenta la última importación fallida (adjunto) o redescarga DGII."""
        Log = self.env["justech.do.rnc.padron.import.log"].sudo()
        last = Log.search([("state", "=", "failed")], order="id desc", limit=1)
        if not last:
            raise UserError(_("No hay una importación fallida reciente para reintentar."))
        if last.file_attachment_id and last.file_attachment_id.datas:
            return last.action_retry_from_attachment()
        return self.run_auto_update(force=True)
