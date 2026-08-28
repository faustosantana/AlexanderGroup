import base64
import hashlib
import logging
import re

from odoo import http
from odoo.exceptions import MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Solo códigos cortos públicos (DOR, PIN, …). Nada de IDs ni rutas.
_CODE_RE = re.compile(r"^[A-Za-z]{2,5}$")


def _logo_content_type(raw):
    if raw.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if raw.startswith(b"GIF8"):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _fallback_svg(label):
    safe = re.sub(r"[^A-Za-z0-9 .+-]", "", label or "DX")[:12] or "DX"
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='64' "
        "viewBox='0 0 160 64' role='img'>"
        "<rect width='160' height='64' rx='8' fill='#0b1f3a'/>"
        "<text x='80' y='38' text-anchor='middle' fill='#c4a35a' "
        "font-family='Segoe UI, Arial, sans-serif' font-size='18'>%s</text>"
        "</svg>" % safe
    ).encode("utf-8")


def _reject_logo():
    """404 de texto plano, sin plantilla Website."""
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


def _serve_published_logo(code):
    raw_code = (code or "").strip()
    if not _CODE_RE.fullmatch(raw_code):
        return _reject_logo()
    company = (
        request.env["res.company"]
        .sudo()
        .search(
            [
                ("dx_short_code", "=", raw_code.upper()),
                ("dx_website_published", "=", True),
            ],
            limit=1,
        )
    )
    if not company:
        return _reject_logo()
    if company.logo:
        raw = base64.b64decode(company.logo)
        ctype = _logo_content_type(raw)
    else:
        raw = _fallback_svg(company.dx_trade_name or company.dx_short_code)
        ctype = "image/svg+xml"
    etag = hashlib.sha256(raw).hexdigest()[:16]
    return request.make_response(
        raw,
        headers=[
            ("Content-Type", ctype),
            ("Content-Length", str(len(raw))),
            ("Cache-Control", "public, max-age=86400"),
            ("X-Content-Type-Options", "nosniff"),
            ("ETag", '"%s"' % etag),
        ],
    )


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
        [
            "/doralex/logo/<string:code>",
            "/doralex/logo/<path:code>",
        ],
        type="http",
        auth="public",
        website=False,
        sitemap=False,
    )
    def company_logo(self, code, **kwargs):
        """Logo público de compañías publicadas. No sirve otros adjuntos."""
        try:
            return _serve_published_logo(code)
        except Exception:
            _logger.info("public logo request rejected")
            return _reject_logo()


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
