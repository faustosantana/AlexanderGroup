# -*- coding: utf-8 -*-
"""Servicio de importación / integridad del padrón RNC DGII."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import logging
import time
import zipfile
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH_SIZE = 5000
# Umbrales de producción (no relajar globalmente).
MIN_FILE_BYTES = 100
MIN_FULL_SOURCE_BYTES = 1024


class JustechDoRncPadronImportService(models.AbstractModel):
    _name = "justech.do.rnc.padron.import.service"
    _description = "Servicio importación padrón RNC"

    # ------------------------------------------------------------------ helpers
    @api.model
    def _require_system(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(
                _(
                    "Solo Administradores del Sistema o Administradores Fiscales "
                    "pueden administrar el padrón DGII."
                )
            )

    @api.model
    def _advisory_lock_key(self, config):
        # Clave estable por singleton de configuración (global).
        return 8_700_000 + int(config.id)

    @api.model
    def _acquire_lock(self, config):
        """Lock concurrente: advisory PG + marca UI lock_until."""
        cr = self.env.cr
        key = self._advisory_lock_key(config)
        try:
            cr.execute(
                "SELECT id FROM justech_do_rnc_padron_config WHERE id=%s FOR UPDATE NOWAIT",
                [config.id],
            )
        except Exception as exc:
            raise UserError(
                _("Hay una actualización de padrón en curso. Intente más tarde.")
            ) from exc
        cr.execute("SELECT pg_try_advisory_lock(%s)", [key])
        if not cr.fetchone()[0]:
            raise UserError(
                _("Hay una actualización de padrón en curso. Intente más tarde.")
            )
        now = fields.Datetime.now()
        if config.lock_until and config.lock_until > now:
            cr.execute("SELECT pg_advisory_unlock(%s)", [key])
            raise UserError(
                _("Hay una actualización de padrón en curso. Intente más tarde.")
            )
        config.with_context(justech_padron_log_allow_write=True).sudo().write(
            {"lock_until": now + timedelta(hours=2), "last_status": "running"}
        )
        self.env.cr.commit()

    @api.model
    def _release_lock(self, config):
        config.with_context(justech_padron_log_allow_write=True).sudo().write(
            {"lock_until": False}
        )
        try:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(%s)", [self._advisory_lock_key(config)]
            )
        except Exception:  # noqa: BLE001
            _logger.exception("No se pudo liberar advisory lock del padrón")

    @api.model
    def file_sha256(self, raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @api.model
    def decode_payload(self, raw: bytes, filename: str = ""):
        """Devuelve (text, encoding). Soporta ZIP con DGII_RNC.TXT."""
        name = (filename or "").lower()
        if name.endswith(".zip") or raw[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                members = [
                    n
                    for n in zf.namelist()
                    if n.lower().endswith((".txt", ".csv")) and not n.endswith("/")
                ]
                if not members:
                    raise UserError(_("El ZIP no contiene un TXT/CSV válido."))
                # Preferir DGII_RNC.TXT
                members.sort(
                    key=lambda n: (0 if "dgii_rnc" in n.lower() else 1, len(n))
                )
                raw = zf.read(members[0])
                filename = members[0]
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return raw.decode(enc), enc, filename
            except UnicodeDecodeError:
                continue
        raise UserError(_("No se pudo decodificar el archivo (UTF-8/Latin-1)."))

    @api.model
    def detect_delimiter(self, sample_line: str) -> str:
        for delim in ("|", "\t", ";", ","):
            if delim in sample_line:
                return delim
        return "|"

    @api.model
    def parse_row(self, row):
        """Parsea fila DGII oficial o formato simple. Retorna dict o None."""
        if not row or not any((c or "").strip() for c in row):
            return None
        rnc_raw = row[0] if len(row) > 0 else ""
        name = (row[1] if len(row) > 1 else "").strip()
        trade = (row[2] if len(row) > 2 else "").strip() or False
        is_dgii = len(row) >= 10 and (row[9] or "").strip().upper() in {
            "ACTIVO",
            "SUSPENDIDO",
            "INACTIVO",
            "ACTIVE",
            "INACTIVE",
        }
        if is_dgii:
            activity = (row[3] if len(row) > 3 else "").strip() or False
            state_raw = (row[9] if len(row) > 9 else "").strip().lower()
            category = (row[10] if len(row) > 10 else "").strip() or False
        else:
            state_raw = (row[3] if len(row) > 3 else "").strip().lower()
            category = (row[4] if len(row) > 4 else "").strip() or False
            activity = (row[5] if len(row) > 5 else "").strip() or False

        Padron = self.env["justech.do.rnc.padron"]
        rnc = Padron.normalize_rnc(rnc_raw)
        if not rnc or not name or len(rnc) not in (9, 11):
            return None
        state = "active"
        if is_dgii:
            if state_raw in ("suspendido", "inactivo", "inactive"):
                state = "inactive"
            elif state_raw in ("activo", "active"):
                state = "active"
            else:
                state = "unknown"
        else:
            if state_raw in ("inactive", "inactivo", "suspendido", "0", "n"):
                state = "inactive"
            elif state_raw and state_raw not in (
                "active",
                "activo",
                "1",
                "s",
                "si",
                "sí",
                "",
                "normal",
            ):
                state = "unknown"
        return {
            "rnc": rnc,
            "name": name[:255],
            "trade_name": (trade[:255] if trade else False),
            "state": state,
            "category": (category[:255] if category else False),
            "economic_activity": (activity[:255] if activity else False),
        }

    @api.model
    def validate_and_stage(self, raw: bytes, filename: str, delimiter=None, has_header=False):
        """Valida archivo y carga staging. No toca padrón productivo."""
        if not raw or not raw.strip():
            raise UserError(_("El archivo está vacío o es demasiado pequeño."))
        # Fixture de prueba: solo con contexto técnico (nunca UI de usuarios reales).
        allow_test_fixture = bool(
            self.env.context.get("justech_padron_allow_test_fixture")
        )
        if not allow_test_fixture and len(raw) < MIN_FILE_BYTES:
            raise UserError(_("El archivo está vacío o es demasiado pequeño."))
        text, encoding, resolved_name = self.decode_payload(raw, filename)
        lines = text.splitlines()
        if not lines:
            raise UserError(_("El archivo no contiene filas."))
        delim = delimiter or self.detect_delimiter(lines[0])
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        rows = list(reader)
        if has_header and rows:
            rows = rows[1:]
        if not rows:
            raise UserError(_("El archivo no tiene datos después del encabezado."))

        file_hash = self.file_sha256(raw)
        seen = set()
        valid = []
        rejected = 0
        dup_in_file = 0
        for row in rows:
            parsed = self.parse_row(row)
            if not parsed:
                rejected += 1
                continue
            if parsed["rnc"] in seen:
                dup_in_file += 1
                continue
            seen.add(parsed["rnc"])
            valid.append(parsed)

        if not valid:
            raise UserError(
                _(
                    "No se encontraron registros válidos. Verifique el formato "
                    "(RNC|Razón social|...|Estado|Categoría)."
                )
            )

        config = self.env["justech.do.rnc.padron.config"].get_config()
        current_count = self.env["justech.do.rnc.padron"].sudo().search_count([])
        keep_ratio = config.min_keep_ratio or 0.90
        fname = (resolved_name or filename or "").upper()
        # Guardia 90%: solo para listados completos (oficial / archivos grandes)
        looks_full = (
            len(valid) >= max(10000, int(current_count * 0.5))
            or "DGII_RNC" in fname
            or self.env.context.get("justech_padron_full_source")
        )
        # En modo fixture de test no exigir tamaño mínimo de fuente completa.
        if (
            looks_full
            and not allow_test_fixture
            and len(raw) < MIN_FULL_SOURCE_BYTES
        ):
            raise UserError(
                _(
                    "El listado completo es demasiado pequeño (%(n)s bytes). "
                    "Verifique la descarga o el archivo fuente."
                )
                % {"n": len(raw)}
            )
        if (
            current_count
            and looks_full
            and len(valid) < int(current_count * keep_ratio)
            and not self.env.context.get("justech_padron_skip_ratio_check")
        ):
            raise UserError(
                _(
                    "El archivo tiene %(n)s registros válidos, menos del %(pct)s%% "
                    "del padrón vigente (%(cur)s). Importación abortada para proteger "
                    "la versión actual."
                )
                % {
                    "n": len(valid),
                    "pct": int(keep_ratio * 100),
                    "cur": current_count,
                }
            )
        err_ratio = rejected / max(1, len(rows))
        if err_ratio > (config.max_error_ratio or 0.05):
            raise UserError(
                _(
                    "Demasiadas filas rechazadas (%(r)s / %(t)s). "
                    "Revise el formato del archivo."
                )
                % {"r": rejected, "t": len(rows)}
            )

        return {
            "filename": resolved_name or filename,
            "encoding": encoding,
            "delimiter": delim,
            "file_hash": file_hash,
            "file_size": len(raw),
            "rows_total": len(rows),
            "valid": valid,
            "rejected": rejected,
            "dup_in_file": dup_in_file,
            "current_count": current_count,
        }

    @api.model
    def preview_diff(self, staged):
        """Compara staging vs padrón actual (conteos)."""
        Padron = self.env["justech.do.rnc.padron"].sudo()
        existing = {
            r.rnc: (r.name, r.trade_name or "", r.state, r.category or "", r.economic_activity or "")
            for r in Padron.search([])
        }
        new = upd = unc = 0
        incoming = set()
        for row in staged["valid"]:
            incoming.add(row["rnc"])
            key = (
                row["name"],
                row["trade_name"] or "",
                row["state"],
                row["category"] or "",
                row["economic_activity"] or "",
            )
            if row["rnc"] not in existing:
                new += 1
            elif existing[row["rnc"]] == key:
                unc += 1
            else:
                upd += 1
        absent = len(set(existing) - incoming)
        return {
            "count_new": new,
            "count_updated": upd,
            "count_unchanged": unc,
            "count_absent": absent,
            "count_rejected": staged["rejected"],
            "dup_in_file": staged["dup_in_file"],
            "total_valid": len(staged["valid"]),
            "current_count": staged["current_count"],
        }

    @api.model
    def _ensure_snapshot_table(self):
        self.env.cr.execute(
            """
            CREATE TABLE IF NOT EXISTS justech_do_rnc_padron_snapshot (
                LIKE justech_do_rnc_padron INCLUDING ALL
            )
            """
        )

    @api.model
    def _save_snapshot(self):
        self._ensure_snapshot_table()
        cr = self.env.cr
        cr.execute("TRUNCATE justech_do_rnc_padron_snapshot")
        cr.execute(
            """
            INSERT INTO justech_do_rnc_padron_snapshot
            SELECT * FROM justech_do_rnc_padron
            """
        )

    @api.model
    def _restore_snapshot(self):
        self._ensure_snapshot_table()
        cr = self.env.cr
        cr.execute("SELECT count(*) FROM justech_do_rnc_padron_snapshot")
        (cnt,) = cr.fetchone()
        if not cnt:
            raise UserError(_("No hay snapshot disponible para revertir."))
        cr.execute("TRUNCATE justech_do_rnc_padron")
        cr.execute(
            """
            INSERT INTO justech_do_rnc_padron
            SELECT * FROM justech_do_rnc_padron_snapshot
            """
        )
        # Reset sequence
        cr.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('justech_do_rnc_padron', 'id'),
                COALESCE((SELECT MAX(id) FROM justech_do_rnc_padron), 1)
            )
            """
        )

    @api.model
    def apply_import(
        self,
        raw: bytes,
        filename: str,
        source="manual",
        delimiter=None,
        has_header=False,
        deactivate_absent=False,
    ):
        """Importación completa: validar → snapshot → upsert por lotes → historial.

        Si la mutación falla tras commits parciales, restaura el snapshot vigente.
        Nunca deja un padrón a medias cuando hay snapshot previo.
        """
        self._require_system()
        config = self.env["justech.do.rnc.padron.config"].get_config()
        self._acquire_lock(config)
        Log = self.env["justech.do.rnc.padron.import.log"].sudo()
        started = fields.Datetime.now()
        t0 = time.time()
        log = Log.create(
            {
                "state": "running",
                "source": source,
                "filename": filename,
                "file_size": len(raw or b""),
                "user_id": self.env.user.id,
                "started_at": started,
                "count_before": self.env["justech.do.rnc.padron"].sudo().search_count([]),
                "version": fields.Datetime.to_string(started),
            }
        )
        # Conservar payload para reintento (fallo o restore).
        try:
            att = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": filename or "padron_dgii.bin",
                        "type": "binary",
                        "datas": base64.b64encode(raw or b""),
                        "res_model": Log._name,
                        "res_id": log.id,
                        "mimetype": "application/octet-stream",
                    }
                )
            )
            log.with_context(justech_padron_log_allow_write=True).write(
                {"file_attachment_id": att.id}
            )
        except Exception:  # noqa: BLE001
            _logger.exception("No se pudo adjuntar payload de padrón al historial")
        self.env.cr.commit()
        snapshot_taken = False
        mutated = False
        try:
            staged = self.validate_and_stage(raw, filename, delimiter, has_header)
            # Mismo hash que última exitosa → sin cambios (no toca padrón vigente)
            last = Log.search(
                [("state", "in", ("done", "done_warn")), ("file_hash", "!=", False)],
                order="id desc",
                limit=1,
            )
            if last and last.file_hash == staged["file_hash"]:
                log.with_context(justech_padron_log_allow_write=True).write(
                    {
                        "state": "done",
                        "filename": staged["filename"],
                        "file_hash": staged["file_hash"],
                        "file_size": staged["file_size"],
                        "encoding": staged["encoding"],
                        "delimiter": staged["delimiter"],
                        "finished_at": fields.Datetime.now(),
                        "duration_seconds": int(time.time() - t0),
                        "total_rows": staged["rows_total"],
                        "total_valid": len(staged["valid"]),
                        "count_unchanged": len(staged["valid"]),
                        "count_after": staged["current_count"],
                        "summary": _("Archivo idéntico a la última importación (mismo hash)."),
                    }
                )
                next_run = config._next_run_datetime() if config.auto_update_enabled else False
                config.with_context(justech_padron_log_allow_write=True).write(
                    {
                        "last_run_at": fields.Datetime.now(),
                        "last_status": "unchanged",
                        "last_message": _("Sin cambios (hash idéntico)."),
                        "retry_count": 0,
                        "next_run_at": next_run,
                    }
                )
                self._release_lock(config)
                self.env.cr.commit()
                return log

            self.preview_diff(staged)
            self._save_snapshot()
            snapshot_taken = True
            self.env.cr.commit()

            Padron = self.env["justech.do.rnc.padron"].sudo()
            sync_date = fields.Datetime.now()
            created = updated = unchanged = 0
            incoming_rncs = []

            existing_map = {
                r.rnc: r
                for r in Padron.with_context(active_test=False).search([])
            }

            batch_create = []
            for i, row in enumerate(staged["valid"], 1):
                incoming_rncs.append(row["rnc"])
                vals = {
                    **row,
                    "source": "dgii_txt",
                    "sync_date": sync_date,
                    "active": True,
                    "review_absent": False,
                }
                ex = existing_map.get(row["rnc"])
                if not ex:
                    batch_create.append(vals)
                    created += 1
                else:
                    same = (
                        (ex.name or "") == (row["name"] or "")
                        and (ex.trade_name or "") == (row["trade_name"] or "")
                        and (ex.state or "") == (row["state"] or "")
                        and (ex.category or "") == (row["category"] or "")
                        and (ex.economic_activity or "")
                        == (row["economic_activity"] or "")
                        and ex.active
                        and not ex.review_absent
                    )
                    if same:
                        unchanged += 1
                    else:
                        ex.write(vals)
                        updated += 1
                        mutated = True
                if len(batch_create) >= BATCH_SIZE:
                    Padron.create(batch_create)
                    batch_create = []
                    mutated = True
                    self.env.cr.commit()
                elif i % BATCH_SIZE == 0:
                    self.env.cr.commit()
            if batch_create:
                Padron.create(batch_create)
                mutated = True
                self.env.cr.commit()

            # Ausentes: marcar revisión (no borrar)
            incoming_set = set(incoming_rncs)
            if incoming_set:
                self.env.cr.execute(
                    """
                    UPDATE justech_do_rnc_padron
                       SET review_absent = TRUE
                     WHERE NOT (rnc = ANY(%s))
                       AND COALESCE(review_absent, FALSE) = FALSE
                    """,
                    [list(incoming_set)],
                )
                absent = self.env.cr.rowcount
                if absent:
                    mutated = True
                self.env.cr.execute(
                    """
                    UPDATE justech_do_rnc_padron
                       SET review_absent = FALSE
                     WHERE rnc = ANY(%s)
                       AND COALESCE(review_absent, FALSE) = TRUE
                    """,
                    [list(incoming_set)],
                )
            else:
                absent = 0
            if deactivate_absent and incoming_set:
                self.env.cr.execute(
                    """
                    UPDATE justech_do_rnc_padron
                       SET active = FALSE
                     WHERE review_absent = TRUE
                    """
                )
                mutated = True

            count_after = Padron.search_count([])
            state = "done_warn" if (staged["rejected"] or absent) else "done"
            summary = _(
                "Nuevos: %(n)s | Actualizados: %(u)s | Sin cambios: %(c)s | "
                "Ausentes (revisión): %(a)s | Rechazados: %(r)s | Total: %(t)s"
            ) % {
                "n": created,
                "u": updated,
                "c": unchanged,
                "a": absent,
                "r": staged["rejected"],
                "t": count_after,
            }
            log.with_context(justech_padron_log_allow_write=True).write(
                {
                    "state": state,
                    "filename": staged["filename"],
                    "file_hash": staged["file_hash"],
                    "file_size": staged["file_size"],
                    "encoding": staged["encoding"],
                    "delimiter": staged["delimiter"],
                    "finished_at": fields.Datetime.now(),
                    "duration_seconds": int(time.time() - t0),
                    "total_rows": staged["rows_total"],
                    "total_valid": len(staged["valid"]),
                    "count_new": created,
                    "count_updated": updated,
                    "count_unchanged": unchanged,
                    "count_absent": absent,
                    "count_rejected": staged["rejected"],
                    "count_after": count_after,
                    "snapshot_available": True,
                    "summary": summary,
                }
            )
            next_run = config._next_run_datetime() if config.auto_update_enabled else False
            config.with_context(justech_padron_log_allow_write=True).write(
                {
                    "last_run_at": fields.Datetime.now(),
                    "last_success_at": fields.Datetime.now(),
                    "last_status": "updated",
                    "last_message": summary,
                    "retry_count": 0,
                    "next_run_at": next_run,
                }
            )
            self._release_lock(config)
            self.env.cr.commit()
            _logger.info("Padrón RNC importado: %s", summary)
            return log
        except Exception as exc:
            self.env.cr.rollback()
            restore_note = ""
            try:
                if snapshot_taken or mutated:
                    self._restore_snapshot()
                    restore_note = _(
                        " Se restauró el padrón vigente (rollback automático)."
                    )
                    self.env.cr.commit()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Fallo crítico: no se pudo restaurar snapshot tras error de importación"
                )
                restore_note = _(
                    " ADVERTENCIA: no se pudo restaurar el snapshot automáticamente."
                )
            try:
                fail_log = Log.browse(log.id)
                if fail_log.exists():
                    fail_log.with_context(justech_padron_log_allow_write=True).write(
                        {
                            "state": "failed",
                            "finished_at": fields.Datetime.now(),
                            "duration_seconds": int(time.time() - t0),
                            "error_message": "%s%s" % (exc, restore_note),
                            "filename": filename,
                            "file_hash": self.file_sha256(raw) if raw else False,
                        }
                    )
                config.invalidate_recordset()
                config.with_context(justech_padron_log_allow_write=True).write(
                    {
                        "last_run_at": fields.Datetime.now(),
                        "last_status": "failed",
                        "last_message": "%s%s" % (exc, restore_note),
                        "lock_until": False,
                    }
                )
                self._release_lock(config)
                self.env.cr.commit()
            except Exception:  # noqa: BLE001
                _logger.exception("No se pudo registrar fallo de importación padrón")
            raise

    @api.model
    def rollback_log(self, log):
        self._require_system()
        log.ensure_one()
        if not log.can_rollback:
            raise UserError(_("Esta importación no admite rollback."))
        config = self.env["justech.do.rnc.padron.config"].get_config()
        self._acquire_lock(config)
        try:
            self._restore_snapshot()
            log.with_context(justech_padron_log_allow_write=True).write(
                {"state": "reverted", "snapshot_available": False}
            )
            config.with_context(justech_padron_log_allow_write=True).write(
                {
                    "last_status": "review_required",
                    "last_message": _("Rollback aplicado a importación %s") % log.display_name,
                    "lock_until": False,
                }
            )
            self.env.cr.commit()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Rollback completado"),
                    "message": _("Se restauró el padrón previo a la última importación."),
                    "type": "success",
                },
            }
        except Exception:
            self._release_lock(config)
            raise

    @api.model
    def integrity_check(self):
        """Verificación de integridad del padrón."""
        Padron = self.env["justech.do.rnc.padron"].sudo()
        config = self.env["justech.do.rnc.padron.config"].get_config()
        Log = self.env["justech.do.rnc.padron.import.log"].sudo()
        count = Padron.search_count([])
        info = Padron.last_sync_info()
        issues = []
        warnings = []
        severity = "ok"

        # Tabla / registros
        if count <= 0:
            issues.append(_("Padrón vacío."))
            severity = "critical"
        # Duplicados RNC (no deberían existir por SQL constraint)
        self.env.cr.execute(
            """
            SELECT rnc, count(*) FROM justech_do_rnc_padron
            GROUP BY rnc HAVING count(*) > 1 LIMIT 5
            """
        )
        dups = self.env.cr.fetchall()
        if dups:
            issues.append(_("Duplicados de RNC en padrón: %s") % len(dups))
            severity = "critical"

        last_log = Log.search([], order="id desc", limit=1)
        last_ok = Log.search(
            [("state", "in", ("done", "done_warn"))], order="id desc", limit=1
        )
        # Cerrar jobs "running" huérfanos cuando el padrón global ya tiene datos.
        # Evita el falso estado vacío/fallido con cientos de miles de RNC cargados.
        now = fields.Datetime.now()
        if last_log and last_log.state == "running":
            lock_expired = not config.lock_until or config.lock_until < now
            started = last_log.started_at or last_log.create_date
            stale = True
            if started:
                stale = (now - started) > timedelta(minutes=30)
            if count > 0 and (lock_expired or stale or last_ok):
                last_log.with_context(justech_padron_log_allow_write=True).write(
                    {
                        "state": "failed",
                        "finished_at": now,
                        "error_message": _(
                            "Importación marcada como huérfana: el padrón global "
                            "ya tiene %(n)s registros. No requiere recarga por empresa."
                        )
                        % {"n": count},
                    }
                )
                if config.last_status == "running":
                    config.with_context(justech_padron_log_allow_write=True).write(
                        {
                            "last_status": "updated" if last_ok else "failed",
                            "lock_until": False,
                            "last_message": _(
                                "Padrón global operativo (%(n)s registros)."
                            )
                            % {"n": count},
                        }
                    )
                last_log = Log.search([], order="id desc", limit=1)

        if last_log and last_log.state == "failed":
            # Fallo reciente sin datos = problema real; con datos + last_ok = aviso suave.
            if count <= 0:
                issues.append(_("Última importación fallida y padrón vacío."))
                severity = "critical"
            elif not last_ok:
                warnings.append(_("Última importación fallida."))
                if severity == "ok":
                    severity = "high"
            # Si hay last_ok y count>0, el fallo residual no degrada el estado global.
        if last_log and last_log.state == "running":
            # Solo crítico si realmente no hay padrón usable.
            if count <= 0:
                issues.append(_("Importación quedó a medias (en proceso)."))
                severity = "critical"
            else:
                warnings.append(
                    _("Hay una importación en curso; el padrón global sigue operativo.")
                )
                if severity == "ok":
                    severity = "medium"

        sync = info.get("sync_date")
        max_age = config.max_age_days or 90
        if sync:
            age = now - sync
            if age > timedelta(days=max_age):
                warnings.append(
                    _("Padrón desactualizado (más de %(d)s días).") % {"d": max_age}
                )
                if severity == "ok":
                    severity = "medium"
        elif count:
            warnings.append(_("Padrón sin fecha de sincronización."))
            if severity == "ok":
                severity = "medium"

        if last_ok and last_ok.count_rejected:
            warnings.append(
                _("Registros rechazados en última carga: %s") % last_ok.count_rejected
            )
            if severity == "ok":
                severity = "low"

        status_visual = "grey"
        if count <= 0:
            status_visual = "red"
        elif severity == "critical":
            status_visual = "red"
        elif severity in ("high", "medium"):
            status_visual = "yellow"
        else:
            status_visual = "green"

        return {
            "severity": severity,
            "status_visual": status_visual,
            "ok": count > 0 and severity != "critical",
            "count": count,
            "sync_date": sync,
            "source": info.get("source"),
            "file_hash": last_ok.file_hash if last_ok else False,
            "filename": last_ok.filename if last_ok else False,
            "file_size": last_ok.file_size if last_ok else 0,
            "user": last_ok.user_id.name if last_ok else False,
            "last_import_at": last_ok.finished_at if last_ok else False,
            "last_import_state": last_ok.state if last_ok else False,
            "issues": issues,
            "warnings": warnings,
            "max_age_days": max_age,
            "never_loaded": not last_ok and count <= 0,
            "is_global": True,
        }

    @api.model
    def status_payload(self):
        """Payload para el Centro Fiscal."""
        integrity = self.integrity_check()
        config = self.env["justech.do.rnc.padron.config"].get_config()
        last_ok = self.env["justech.do.rnc.padron.import.log"].sudo().search(
            [("state", "in", ("done", "done_warn"))], order="id desc", limit=1
        )
        labels = {
            "green": _("Padrón global cargado y vigente"),
            "yellow": _("Padrón global operativo con advertencias"),
            "red": _("Padrón vacío o importación fallida"),
            "grey": _("Nunca cargado"),
        }
        visual = integrity["status_visual"]
        if integrity["never_loaded"]:
            visual = "grey"
        elif integrity.get("count", 0) > 0 and visual == "red" and not integrity.get("issues"):
            # Defensa: con datos y sin issues reales no mostrar vacío/fallido.
            visual = "yellow" if integrity.get("warnings") else "green"
        guide = _(
            "El padrón DGII es global y compartido por todas las empresas. "
            "No se carga un padrón por compañía. Un solo historial y un solo cron."
        )
        if integrity.get("never_loaded") or integrity.get("count", 0) <= 0:
            guide = _(
                "Después de restaurar una base sin padrón DGII, utilice "
                "Importar padrón DGII (una sola vez, global) para reactivar la validación de RNC."
            )
        return {
            **integrity,
            "status_visual": visual,
            "status_label": labels.get(visual, visual),
            "auto_update_enabled": config.auto_update_enabled,
            "frequency_days": config.frequency_days,
            "run_hour": config.run_hour,
            "cron_active": config._cron_is_active(),
            "last_run_at": config.last_run_at,
            "next_run_at": config.next_run_at,
            "last_status": config.last_status,
            "last_message": config.last_message,
            "official_url": config.official_url,
            "needs_reimport": bool(
                integrity.get("never_loaded") or integrity.get("count", 0) <= 0
            ),
            "file_hash_last": last_ok.file_hash if last_ok else False,
            "count_new_last": last_ok.count_new if last_ok else 0,
            "count_updated_last": last_ok.count_updated if last_ok else 0,
            "count_rejected_last": last_ok.count_rejected if last_ok else 0,
            "guide": guide,
        }
