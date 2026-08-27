from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminOperation(models.Model):
    _name = "justech.admin.operation"
    _description = "Operación controlada Justech Admin"
    _order = "id desc"

    name = fields.Char(required=True)
    module_id = fields.Many2one("justech.admin.module", required=True, ondelete="cascade")
    operation_type = fields.Selection(
        selection=[
            ("install", "Instalar"),
            ("activate", "Activar"),
            ("deactivate", "Desactivar"),
            ("configure", "Configurar"),
            ("role_change", "Cambio de roles"),
        ],
        required=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("preview", "Previsualización"),
            ("running", "En ejecución"),
            ("done", "Completada"),
            ("failed", "Fallida"),
            ("rolled_back", "Revertida"),
        ],
        default="draft",
        required=True,
    )
    company_ids = fields.Many2many("res.company", string="Empresas afectadas")
    preview_before = fields.Text()
    preview_after = fields.Text()
    risks = fields.Text()
    rollback_notes = fields.Text()
    backup_path = fields.Char()
    result_message = fields.Text()
    error_message = fields.Text()
    executed_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    started_at = fields.Datetime()
    finished_at = fields.Datetime()

    def action_mark_preview(self):
        self.write({"state": "preview"})

    @api.model
    def _acquire_lock(self):
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s)", [88442201])
        if not self.env.cr.fetchone()[0]:
            raise UserError(
                _("Ya hay una operación de módulos en curso. Espere a que finalice.")
            )
        running = self.search_count([("state", "=", "running")])
        if running:
            raise UserError(
                _("Ya hay una operación de módulos en curso. Espere a que finalice.")
            )

    def action_execute(self):
        self.ensure_one()
        if self.state not in ("preview", "draft"):
            raise UserError(_("Solo se pueden ejecutar operaciones en borrador o previsualización."))
        self._acquire_lock()
        self.write(
            {
                "state": "running",
                "started_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        try:
            if self.operation_type == "install":
                result = self.env["justech.admin.install.service"].execute(self)
            elif self.operation_type == "activate":
                result = self.env["justech.admin.activation.service"].activate(self)
            elif self.operation_type == "deactivate":
                result = self.env["justech.admin.activation.service"].deactivate(self)
            else:
                raise UserError(_("Tipo de operación no soportado en esta versión."))
            self.write(
                {
                    "state": "done",
                    "finished_at": fields.Datetime.now(),
                    "result_message": result.get("message"),
                    "backup_path": result.get("backup_path"),
                }
            )
            self.env["justech.admin.audit.log"].sudo().log_operation(self, result)
            return result.get("action") or True
        except Exception as exc:
            self.write(
                {
                    "state": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_message": str(exc),
                }
            )
            self.env["justech.admin.audit.log"].sudo().log_operation(
                self, {"message": str(exc), "ok": False}
            )
            raise
