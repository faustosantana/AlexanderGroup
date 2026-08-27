from odoo import api, fields, models, _


class JustechAdminAuthWizard(models.TransientModel):
    _name = "justech.admin.auth.wizard"
    _description = "Reautenticación Administración Justech"

    password = fields.Char(string="Clave maestra", password=True)
    info = fields.Html(
        default=lambda self: _(
            "<p>El acceso a <strong>Administración Justech</strong> requiere usuario autorizado "
            "y la clave maestra del propietario.</p>"
            "<p>La sesión dura 15 minutos y no se almacena la clave.</p>"
        ),
        sanitize=False,
    )

    @api.model
    def action_open(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Autenticación Administración Justech"),
            "res_model": "justech.admin.auth.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_unlock(self):
        self.ensure_one()
        self.env["justech.admin.center.auth.service"].verify_and_open_session(self.password)
        self.password = False
        return self.env["justech.admin.console"].action_open_console()
