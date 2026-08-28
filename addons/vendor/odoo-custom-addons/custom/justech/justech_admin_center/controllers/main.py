# -*- coding: utf-8 -*-
"""Sincroniza empresa de sesión Odoo (cookie cids) con el filtro de la consola."""

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class JustechAdminConsoleController(http.Controller):

    @http.route(
        "/justech/admin/console/company/<int:company_id>",
        type="http",
        auth="user",
        methods=["GET"],
        sitemap=False,
    )
    def switch_console_company(self, company_id, console_id=None, **kwargs):
        """Una sola fuente de contexto: cookie cids + company_id + filtro consola."""
        env = request.env
        Auth = env["justech.admin.center.auth.service"]
        try:
            Auth.require_authorized_user()
        except (AccessError, UserError):
            return request.redirect("/odoo")

        company = env["res.company"].browse(company_id)
        user = env.user
        if not company.exists() or company not in user.company_ids:
            raise AccessError(
                _("No tiene acceso a la empresa %(company)s.")
                % {"company": company.display_name if company.exists() else company_id}
            )

        if user.company_id != company:
            user.with_context(allowed_company_ids=user.company_ids.ids).sudo().write(
                {"company_id": company.id}
            )

        console = env["justech.admin.console"]._ensure_singleton()
        if console_id:
            candidate = env["justech.admin.console"].browse(int(console_id))
            if candidate.exists():
                console = candidate
        console.sudo().write({"filter_company_id": company.id})

        # Odoo 19 lee la empresa activa desde cookie `cids` (primer id = activa).
        # El query ?cids= en URL no actualiza esa cookie; hay que setearla aquí.
        request.future_response.set_cookie("cids", str(company.id), path="/")
        return request.redirect("/odoo/justech.admin.console/%s" % console.id)
