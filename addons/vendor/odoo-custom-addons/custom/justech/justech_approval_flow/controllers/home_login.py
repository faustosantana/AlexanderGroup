# -*- coding: utf-8 -*-
"""Sanitize login redirect for approval links + session-expired UX message."""

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import request

from odoo.addons.justech_approval_flow.controllers.approval_controller import (
    safe_approval_redirect_path,
)


class JustechApprovalHome(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        # Block open redirects; keep only internal approval paths from our flow.
        if redirect:
            safe = safe_approval_redirect_path(redirect)
            if redirect.startswith("/justech/approval/") and not safe:
                redirect = "/odoo"
            elif safe:
                redirect = safe
            elif redirect.startswith(("http://", "https://", "//")):
                # never bounce to external hosts from this entry
                redirect = "/odoo"
        response = super().web_login(redirect=redirect, **kw)
        # Inject friendly banner when returning from expired approval session
        try:
            if (
                request.httprequest.method == "GET"
                and request.params.get("justech_approval_session")
                and hasattr(response, "qcontext")
            ):
                response.qcontext = dict(response.qcontext or {})
                response.qcontext["error"] = (
                    "Tu sesión ha expirado. Inicia sesión nuevamente para continuar "
                    "con la aprobación. No se ejecutará ninguna acción automáticamente."
                )
        except Exception:  # noqa: BLE001
            pass
        return response
