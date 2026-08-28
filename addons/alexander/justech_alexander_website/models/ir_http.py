from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

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
