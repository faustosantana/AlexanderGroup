from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _frontend_pre_dispatch(cls):
        """Keep assigned companies readable on the public site.

        Native website pins allowed_company_ids to the website company
        (Doralex). A logged-in user whose switcher is another assigned
        company then gets AccessError reading that company on GET /.
        Do not grant unassigned companies and do not change ir.rule.
        """
        super()._frontend_pre_dispatch()
        user = request.env.user
        if user._is_public():
            return
        website = getattr(request, "website", None)
        if website is None:
            return
        assigned = list(user._get_company_ids())
        if not assigned:
            return
        website_company_id = website._get_cached("company_id")
        allowed = []
        if website_company_id in assigned:
            allowed.append(website_company_id)
        allowed.extend(cid for cid in assigned if cid not in allowed)
        request.update_context(allowed_company_ids=allowed)
        request.website = website.with_context(request.env.context)

    @classmethod
    def _handle_error(cls, exception):
        path = ""
        try:
            path = request.httprequest.path or ""
        except Exception:
            path = ""
        if path.startswith("/doralex/"):
            response = request.make_response(
                b"Not found",
                headers=[
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Cache-Control", "no-store"),
                    ("X-Content-Type-Options", "nosniff"),
                ],
            )
            response.status_code = 404
            return response
        return super()._handle_error(exception)
