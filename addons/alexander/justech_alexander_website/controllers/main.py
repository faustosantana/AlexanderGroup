import base64

from odoo import http
from odoo.exceptions import MissingError
from odoo.http import request


def _logo_content_type(raw):
    if raw.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if raw.startswith(b"GIF8"):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


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

    @http.route(
        ["/doralex/logo/<string:code>"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def company_logo(self, code, **kwargs):
        """Sirve el logo público sin filtrar por company isolation de /web/image."""
        company = (
            request.env["res.company"]
            .sudo()
            .search(
                [
                    ("dx_short_code", "=", (code or "").strip().upper()),
                    ("dx_website_published", "=", True),
                ],
                limit=1,
            )
        )
        if not company or not company.logo:
            raise MissingError("Logo no disponible")
        raw = base64.b64decode(company.logo)
        return request.make_response(
            raw,
            headers=[
                ("Content-Type", _logo_content_type(raw)),
                ("Content-Length", str(len(raw))),
                ("Cache-Control", "public, max-age=86400"),
                ("X-Content-Type-Options", "nosniff"),
            ],
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
