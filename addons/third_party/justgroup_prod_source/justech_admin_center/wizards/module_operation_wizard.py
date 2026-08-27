from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminModuleOperationWizard(models.TransientModel):
    _name = "justech.admin.module.operation.wizard"
    _description = "Previsualización instalación/activación Justech"

    module_id = fields.Many2one("justech.admin.module", required=True)
    operation_type = fields.Selection(
        selection=[
            ("install", "Instalar"),
            ("activate", "Activar"),
            ("deactivate", "Desactivar"),
        ],
        required=True,
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Empresas afectadas",
        default=lambda self: self.env.companies,
    )
    preview_before = fields.Text(readonly=True)
    preview_after = fields.Text(readonly=True)
    dependencies = fields.Text(readonly=True)
    risks = fields.Text(readonly=True)
    rollback_notes = fields.Text(readonly=True)
    estimated_minutes = fields.Integer(readonly=True)
    confirmation = fields.Boolean(string="Confirmo que he leído riesgos y backup")

    @api.model
    def action_open_for_module(self, module, operation_type):
        wiz = self.create({"module_id": module.id, "operation_type": operation_type})
        wiz._load_preview()
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirmar: %s") % dict(self._fields["operation_type"].selection).get(operation_type),
            "res_model": self._name,
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
        }

    def _load_preview(self):
        self.ensure_one()
        if self.operation_type == "install":
            data = self.env["justech.admin.install.service"].build_preview(self.module_id)
            self.write(
                {
                    "preview_before": data["before"],
                    "preview_after": data["after"],
                    "dependencies": data["dependencies"],
                    "risks": data["risks"],
                    "rollback_notes": data["rollback"],
                    "estimated_minutes": data["estimated_minutes"],
                }
            )
        else:
            data = self.env["justech.admin.activation.service"].build_preview(
                self.module_id, self.operation_type
            )
            self.write(
                {
                    "preview_before": data["before"],
                    "preview_after": data["after"],
                    "dependencies": self.module_id.dependency_names or "",
                    "risks": data["risks"],
                    "rollback_notes": data["rollback"],
                    "estimated_minutes": 1,
                }
            )

    def action_apply(self):
        self.ensure_one()
        self.env["justech.admin.center.auth.service"].require_session()
        if not self.confirmation:
            raise UserError(_("Debe confirmar que ha leído riesgos y backup."))
        if self.operation_type == "install" and not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("justech_admin_center.group_justech_admin_center_manager")
        ):
            raise UserError(_("Solo Administradores del Sistema / Justech pueden instalar módulos."))

        op = self.env["justech.admin.operation"].create(
            {
                "name": "%s %s" % (self.operation_type, self.module_id.technical_name),
                "module_id": self.module_id.id,
                "operation_type": self.operation_type,
                "state": "preview",
                "company_ids": [(6, 0, self.company_ids.ids)],
                "preview_before": self.preview_before,
                "preview_after": self.preview_after,
                "risks": self.risks,
                "rollback_notes": self.rollback_notes,
            }
        )
        op.action_execute()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Operación completada"),
                "message": op.result_message or _("OK"),
                "type": "success",
                "next": self.env["justech.admin.console"].action_open_console(),
            },
        }
