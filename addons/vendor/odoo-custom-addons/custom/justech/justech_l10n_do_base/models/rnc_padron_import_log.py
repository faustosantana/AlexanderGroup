# -*- coding: utf-8 -*-
"""Historial de importaciones del padrón RNC DGII."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import base64


class JustechDoRncPadronImportLog(models.Model):
    _name = "justech.do.rnc.padron.import.log"
    _description = "Historial importación padrón RNC"
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    state = fields.Selection(
        [
            ("running", "En proceso"),
            ("done", "Completado"),
            ("done_warn", "Completado con advertencias"),
            ("failed", "Fallido"),
            ("reverted", "Revertido"),
        ],
        string="Estado",
        default="running",
        required=True,
        index=True,
        copy=False,
    )
    source = fields.Selection(
        [
            ("manual", "Importación manual"),
            ("update", "Actualización manual"),
            ("auto", "Actualización automática"),
            ("retry", "Reintento"),
            ("rollback", "Rollback"),
        ],
        string="Fuente",
        required=True,
        default="manual",
    )
    filename = fields.Char(string="Nombre del archivo")
    file_size = fields.Integer(string="Tamaño (bytes)")
    file_hash = fields.Char(string="Hash SHA-256", index=True)
    encoding = fields.Char(string="Codificación")
    delimiter = fields.Char(string="Separador")
    file_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo fuente",
        readonly=True,
        ondelete="set null",
        help="Payload conservado para reintento / reimportación tras restore.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    started_at = fields.Datetime(string="Inicio", default=fields.Datetime.now, readonly=True)
    finished_at = fields.Datetime(string="Fin", readonly=True)
    duration_seconds = fields.Integer(string="Duración (seg)", readonly=True)
    version = fields.Char(string="Versión", readonly=True)
    total_rows = fields.Integer(string="Filas leídas", readonly=True)
    total_valid = fields.Integer(string="Registros válidos", readonly=True)
    count_new = fields.Integer(string="Nuevos", readonly=True)
    count_updated = fields.Integer(string="Actualizados", readonly=True)
    count_unchanged = fields.Integer(string="Sin cambios", readonly=True)
    count_absent = fields.Integer(string="Ausentes (revisión)", readonly=True)
    count_rejected = fields.Integer(string="Rechazados", readonly=True)
    count_before = fields.Integer(string="Total previo", readonly=True)
    count_after = fields.Integer(string="Total posterior", readonly=True)
    error_message = fields.Text(string="Mensaje de error", readonly=True)
    summary = fields.Text(string="Resumen", readonly=True)
    snapshot_available = fields.Boolean(
        string="Snapshot disponible para rollback",
        default=False,
        readonly=True,
    )
    can_rollback = fields.Boolean(compute="_compute_can_rollback")

    @api.depends("started_at", "filename", "state")
    def _compute_display_name(self):
        for rec in self:
            when = fields.Datetime.to_string(rec.started_at) if rec.started_at else ""
            rec.display_name = _("%(file)s — %(when)s (%(state)s)") % {
                "file": rec.filename or _("sin archivo"),
                "when": when,
                "state": dict(rec._fields["state"].selection).get(rec.state, rec.state),
            }

    @api.depends("state", "snapshot_available")
    def _compute_can_rollback(self):
        latest_ok = self.search(
            [("state", "in", ("done", "done_warn")), ("snapshot_available", "=", True)],
            order="id desc",
            limit=1,
        )
        for rec in self:
            rec.can_rollback = bool(
                latest_ok
                and rec.id == latest_ok.id
                and rec.state in ("done", "done_warn")
                and rec.snapshot_available
            )

    def write(self, vals):
        # Historial inmutable tras cierre (salvo rollback interno vía sudo/context).
        if not self.env.context.get("justech_padron_log_allow_write"):
            protected = self.filtered(lambda r: r.state in ("done", "done_warn", "failed", "reverted"))
            if protected and set(vals) - {"display_name"}:
                raise UserError(
                    _("El historial de importación no puede editarse manualmente.")
                )
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("justech_padron_log_allow_unlink"):
            raise UserError(_("No se puede eliminar el historial de importación."))
        return super().unlink()

    def action_rollback(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(
                _(
                    "Solo Administradores del Sistema o Administradores Fiscales "
                    "pueden revertir el padrón."
                )
            )
        return self.env["justech.do.rnc.padron.import.service"].rollback_log(self)

    def action_retry_from_attachment(self):
        """Reaplica el archivo adjunto de esta importación fallida."""
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(
                _("Solo administradores autorizados pueden reintentar la importación.")
            )
        if not self.file_attachment_id or not self.file_attachment_id.datas:
            raise UserError(
                _(
                    "No hay archivo adjunto para reintentar. "
                    "Use «Actualizar ahora» para descargar desde la DGII."
                )
            )
        raw = base64.b64decode(self.file_attachment_id.datas)
        return self.env["justech.do.rnc.padron.import.service"].apply_import(
            raw,
            self.filename or self.file_attachment_id.name or "retry.bin",
            source="retry",
            delimiter=self.delimiter or None,
            has_header=False,
        )
