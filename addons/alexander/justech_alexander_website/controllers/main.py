from odoo import http
from odoo.http import request
from odoo.exceptions import MissingError


class DoralexWebsite(http.Controller):
    @http.route(
        ["/empresas/<string:code>"],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def company_detail(self, code, **kwargs):
        payload = request.env["res.company"].sudo()._dx_public_company(code)
        if not payload:
            raise MissingError("Empresa no disponible")
        return request.render(
            "justech_alexander_website.company_detail",
            {
                "dx": payload,
                "dx_contact": _group_contact(),
            },
        )


def _group_contact():
    company = (
        request.env["res.company"]
        .sudo()
        .search(
            [("dx_short_code", "=", "DOR")],
            limit=1,
        )
    )
    if not company:
        company = request.env.company.sudo()
    return {
        "name": company.dx_trade_name or "Doralex Group",
        "phone": company.phone or "",
        "email": company.email or "",
        "city": company.city or "",
    }
