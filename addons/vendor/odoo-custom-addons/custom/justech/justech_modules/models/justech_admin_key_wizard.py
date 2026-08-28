from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechAdminKeyWizard(models.TransientModel):
    _name = "justech.admin.key.wizard"
    _description = "Justech Administrative Key Prompt"

    admin_key = fields.Char(string="Clave Administrativa Justech", required=True)
    scope = fields.Char(default="platform")
    target_action_xmlid = fields.Char()
    target_method = fields.Char()
    prompt_message = fields.Text(
        string="Mensaje",
        readonly=True,
        default=lambda self: _(
            "Introduzca la Clave Administrativa Justech para continuar."
        ),
    )

    def action_verify(self):
        self.ensure_one()
        service = self.env["justech.admin.access.service"]
        if not service.user_has_key():
            return service._action_setup_key_required(
                self.target_action_xmlid, self.scope
            )
        if not self.admin_key:
            raise UserError(_("Introduzca la Clave Administrativa Justech."))
        service.open_session(self.admin_key, scope=self.scope)
        if self.target_method:
            method = getattr(service, self.target_method, None)
            if not method:
                raise UserError(_("Acción protegida no disponible."))
            return method()
        if not self.target_action_xmlid:
            raise UserError(_("Acción protegida no disponible."))
        return service._resolve_action(self.target_action_xmlid)
