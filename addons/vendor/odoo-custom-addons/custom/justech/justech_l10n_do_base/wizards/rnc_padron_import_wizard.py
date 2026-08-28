# -*- coding: utf-8 -*-
"""Wizard de importación / actualización del padrón RNC (solo Administradores)."""
from __future__ import annotations

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class JustechDoRncPadronImportWizard(models.TransientModel):
    _name = "justech.do.rnc.padron.import.wizard"
    _description = "Importar / actualizar padrón RNC DGII"

    data_file = fields.Binary(string="Archivo TXT/CSV/ZIP")
    filename = fields.Char(string="Nombre de archivo")
    delimiter = fields.Selection(
        [
            ("|", "Pipe |"),
            (",", "Coma ,"),
            (";", "Punto y coma ;"),
            ("\t", "Tabulador"),
            ("auto", "Detectar automáticamente"),
        ],
        string="Separador",
        default="auto",
        required=True,
    )
    has_header = fields.Boolean(string="Primera fila es encabezado", default=False)
    mode = fields.Selection(
        [
            ("import", "Importar padrón DGII"),
            ("update", "Actualizar padrón DGII"),
        ],
        string="Modo",
        default="import",
        required=True,
    )
    # Preview
    preview_done = fields.Boolean(readonly=True)
    file_hash = fields.Char(string="Hash SHA-256", readonly=True)
    file_size = fields.Integer(string="Tamaño", readonly=True)
    encoding = fields.Char(string="Codificación", readonly=True)
    preview_summary = fields.Text(string="Resumen de validación", readonly=True)
    count_new = fields.Integer(readonly=True)
    count_updated = fields.Integer(readonly=True)
    count_unchanged = fields.Integer(readonly=True)
    count_absent = fields.Integer(readonly=True)
    count_rejected = fields.Integer(readonly=True)
    total_valid = fields.Integer(readonly=True)
    result_log = fields.Text(string="Resultado", readonly=True)
    last_log_id = fields.Many2one(
        "justech.do.rnc.padron.import.log", string="Último historial", readonly=True
    )

    def _raw(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Seleccione un archivo."))
        return base64.b64decode(self.data_file)

    def action_validate_preview(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(_("Solo Administradores Fiscales pueden importar el padrón."))
        svc = self.env["justech.do.rnc.padron.import.service"]
        delim = False if self.delimiter == "auto" else self.delimiter
        staged = svc.validate_and_stage(
            self._raw(), self.filename or "padron.txt", delim, self.has_header
        )
        diff = svc.preview_diff(staged)
        self.write(
            {
                "preview_done": True,
                "file_hash": staged["file_hash"],
                "file_size": staged["file_size"],
                "encoding": staged["encoding"],
                "count_new": diff["count_new"],
                "count_updated": diff["count_updated"],
                "count_unchanged": diff["count_unchanged"],
                "count_absent": diff["count_absent"],
                "count_rejected": diff["count_rejected"],
                "total_valid": diff["total_valid"],
                "preview_summary": _(
                    "Archivo: %(f)s\n"
                    "Hash: %(h)s\n"
                    "Válidos: %(v)s | Rechazados: %(r)s | Duplicados en archivo: %(d)s\n"
                    "Nuevos: %(n)s | Actualizados: %(u)s | Sin cambios: %(c)s | "
                    "Ausentes (revisión): %(a)s\n"
                    "Padrón actual: %(cur)s registros\n\n"
                    "No se modificarán contactos, facturas ni datos históricos."
                )
                % {
                    "f": staged["filename"],
                    "h": staged["file_hash"],
                    "v": diff["total_valid"],
                    "r": diff["count_rejected"],
                    "d": staged["dup_in_file"],
                    "n": diff["count_new"],
                    "u": diff["count_updated"],
                    "c": diff["count_unchanged"],
                    "a": diff["count_absent"],
                    "cur": diff["current_count"],
                },
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm_import(self):
        self.ensure_one()
        if not self.preview_done:
            raise UserError(_("Valide el archivo antes de confirmar."))
        svc = self.env["justech.do.rnc.padron.import.service"]
        delim = False if self.delimiter == "auto" else self.delimiter
        source = "update" if self.mode == "update" else "manual"
        log = svc.apply_import(
            self._raw(),
            self.filename or "padron.txt",
            source=source,
            delimiter=delim,
            has_header=self.has_header,
        )
        self.write(
            {
                "result_log": log.summary or log.error_message or _("Importación finalizada."),
                "last_log_id": log.id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_history(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Historial padrón DGII"),
            "res_model": "justech.do.rnc.padron.import.log",
            "view_mode": "list,form",
            "target": "current",
        }
