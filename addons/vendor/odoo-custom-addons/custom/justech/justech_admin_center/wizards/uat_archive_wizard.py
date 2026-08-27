from odoo import api, fields, models, _
from odoo.exceptions import UserError
import re


UAT_PATTERN = re.compile(
    r"(uat|test|ux\s*shot|shot_admin|padr[oó]n|std\b|prueba)",
    re.IGNORECASE,
)


class JustechAdminUatArchiveWizard(models.TransientModel):
    _name = "justech.admin.uat.archive.wizard"
    _description = "Archivar usuarios de prueba Justech"

    user_ids = fields.Many2many(
        "res.users",
        string="Usuarios de prueba a archivar",
        domain=[("justech_is_test_user", "=", True), ("active", "=", True)],
    )
    preview_html = fields.Html(readonly=True, sanitize=False)
    confirmation = fields.Boolean(
        string="Confirmo archivar solo cuentas de prueba (no usuarios reales)"
    )

    @api.model
    def action_open(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        users = self.env["res.users"].sudo().search(
            [("share", "=", False), ("justech_is_test_user", "=", True), ("active", "=", True)]
        )
        wiz = self.create({"user_ids": [(6, 0, users.ids)]})
        wiz._build_preview()
        return {
            "type": "ir.actions.act_window",
            "name": _("Archivar usuarios de prueba"),
            "res_model": self._name,
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
        }

    def _build_preview(self):
        rows = []
        for u in self.user_ids:
            rows.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    u.name,
                    u.login,
                    u.justech_test_role_label or "—",
                    ", ".join(u.company_ids.mapped("name")[:3]) or "—",
                    u.login_date or "—",
                )
            )
        self.preview_html = (
            "<p>%s</p>"
            '<table class="table table-sm o_jac_table">'
            "<thead><tr><th>Nombre</th><th>Usuario</th><th>Rol probado</th>"
            "<th>Empresa</th><th>Última actividad</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            "<p><strong>%s</strong></p>"
        ) % (
            _("Se archivarán %s cuentas de prueba. Los usuarios reales no se modifican.")
            % len(self.user_ids),
            "".join(rows) or "<tr><td colspan='5'>%s</td></tr>" % _("Ninguna"),
            _("Las cuentas quedarán inactivas y no deben copiarse a Producción."),
        )

    @api.onchange("user_ids")
    def _onchange_users(self):
        self._build_preview()

    def action_archive(self):
        self.ensure_one()
        self.env["justech.admin.center.auth.service"].require_session()
        if not self.confirmation:
            raise UserError(_("Confirme el archivado de usuarios de prueba."))
        # Safety: never archive non-test or admin system alone blindly
        targets = self.user_ids.filtered(lambda u: u.justech_is_test_user and u.active)
        if not targets:
            raise UserError(_("No hay usuarios de prueba seleccionados."))
        real = targets.filtered(lambda u: not u.justech_is_test_user)
        if real:
            raise UserError(_("Se detectaron usuarios que no son de prueba. Operación cancelada."))
        before = ", ".join(targets.mapped("login"))
        targets.sudo().write({"active": False})
        self.env["justech.admin.audit.log"].sudo().log_simple(
            summary=_("Archivo de usuarios de prueba (%s)") % len(targets),
            operation="uat_archive",
            state_before=before,
            state_after=_("Inactivos"),
            reason=_("Archivado desde Administración Justech"),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Usuarios de prueba archivados"),
                "message": _("%s cuentas inactivadas.") % len(targets),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


def classify_test_user(user):
    blob = "%s %s" % (user.login or "", user.name or "")
    return bool(UAT_PATTERN.search(blob))
