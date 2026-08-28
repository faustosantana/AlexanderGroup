# -*- coding: utf-8 -*-
"""Mail approval links: require login, keep CSRF, friendly session UX."""

import logging
import re
from urllib.parse import urlparse

from markupsafe import escape
from werkzeug.exceptions import BadRequest, HTTPException

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request, SessionExpiredException

_logger = logging.getLogger(__name__)

# Only relative /justech/approval/<token>/(approve|reject) — no open redirect.
_SAFE_APPROVAL_REDIRECT = re.compile(
    r"^/justech/approval/[A-Za-z0-9_\-]+/(approve|reject)/?$"
)


def _fmt_amount(rec):
    if rec.currency_id:
        return rec.currency_id.format(rec.amount_total or 0.0)
    return "%.2f" % (rec.amount_total or 0.0)


def _esc(val):
    return str(escape(val if val is not None else ""))


def safe_approval_redirect_path(path_or_url):
    """Return an internal approval path or False (blocks open redirects)."""
    if not path_or_url:
        return False
    raw = path_or_url.strip()
    if raw.startswith("//") or "://" in raw:
        parsed = urlparse(raw)
        # allow same-host absolute URLs that map to approval path
        path = parsed.path or ""
    else:
        path = raw.split("?", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    if _SAFE_APPROVAL_REDIRECT.match(path):
        return path
    return False


def _login_redirect_for_approval(path):
    """Send user to login, then back to the approval GET page (never auto-approve)."""
    safe = safe_approval_redirect_path(path) or "/odoo"
    return request.redirect_query(
        "/web/login",
        {
            "redirect": safe,
            "justech_approval_session": "1",
        },
    )


def _forbidden_page(message, brand="JUSTECH"):
    return _page(
        _("Acceso denegado"),
        "<p>%s</p>" % _esc(message),
        status=403,
        brand=brand,
    )


def _page(title, body_html, status=200, brand="JUSTECH"):
    html = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>%(title)s</title>
</head>
<body style="margin:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%%;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
        <tr><td style="padding:20px 24px;background:#1e3a5f;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:.06em;">%(brand)s</td></tr>
        <tr><td style="padding:24px;">%(body)s</td></tr>
        <tr><td style="padding:16px 24px;background:#f8fafc;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
          Solicitud interna de aprobación en Odoo. Requiere inicio de sesión.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""" % {"title": _esc(title), "body": body_html, "brand": _esc(brand)}
    return request.make_response(
        html,
        headers=[("Content-Type", "text/html; charset=utf-8")],
        status=status,
    )


def _summary_block(rec):
    partner_label = _("Proveedor") if rec.request_type == "purchase_order" else _("Cliente")
    type_label = {
        "purchase_order": _("Orden de compra"),
        "sale_order": _("Cotización"),
        "out_invoice": _("Factura de cliente"),
    }.get(rec.request_type, rec.request_type or "")
    note_html = ""
    if rec.request_note:
        note_html = """
        <div style="margin-top:12px;padding:12px 14px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">
          <div style="font-size:11px;color:#92400e;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">Comentario del solicitante</div>
          <div style="color:#78350f;">%s</div>
        </div>
        """ % rec.request_note_html()
    att_html = ""
    if rec.attachment_count:
        names = "".join(
            "<li>%s</li>" % _esc(att.name or _("archivo")) for att in rec.attachment_ids
        )
        att_html = """
        <div style="margin-top:12px;font-size:14px;">
          <strong>Adjuntos: %s</strong>
          <ul style="margin:8px 0 0 18px;padding:0;">%s</ul>
          <div style="font-size:12px;color:#6b7280;margin-top:6px;">Ábralos desde Odoo con una sesión autenticada.</div>
        </div>
        """ % (rec.attachment_count, names)
    return """
    <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:20px;">
      <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.08em;">%(type)s</div>
      <div style="font-size:20px;font-weight:700;margin:4px 0 12px 0;">%(doc)s</div>
      <table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="font-size:14px;">
        <tr><td style="color:#6b7280;padding:4px 0;width:140px;">%(partner_label)s</td>
            <td style="padding:4px 0;">%(partner)s</td></tr>
        <tr><td style="color:#6b7280;padding:4px 0;">%(total_label)s</td>
            <td style="padding:4px 0;font-size:18px;font-weight:700;">%(amount)s</td></tr>
        <tr><td style="color:#6b7280;padding:4px 0;">%(requested_label)s</td>
            <td style="padding:4px 0;">%(requester)s</td></tr>
      </table>
      %(note)s
      %(atts)s
    </div>
    """ % {
        "type": _esc(type_label),
        "doc": _esc(rec.document_name or rec.display_name),
        "partner_label": _esc(partner_label),
        "partner": _esc(rec.partner_id.display_name or "-"),
        "total_label": _esc(_("Total")),
        "amount": _esc(_fmt_amount(rec)),
        "requested_label": _esc(_("Solicitado por")),
        "requester": _esc(rec.requester_id.name or "-"),
        "note": note_html,
        "atts": att_html,
    }


class JustechApprovalController(http.Controller):
    def _request_or_error(self, token):
        Request = request.env["justech.approval.request"].sudo()
        error = Request._token_error(token)
        rec = Request._find_by_raw_token(token)
        return rec, error

    def _ensure_authenticated(self):
        """auth=user already enforces this; belt-and-suspenders for public uid."""
        user = request.env.user
        if not user or user._is_public() or not request.session.uid:
            raise SessionExpiredException("Session expired")

    @http.route(
        "/justech/approval/<string:token>/approve",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        csrf=True,
    )
    def approve(self, token, **post):
        self._ensure_authenticated()
        rec, error = self._request_or_error(token)
        if error:
            return _page(
                _("Solicitud no válida"),
                "<p>%s</p>" % _esc(error),
                status=400,
                brand=(rec._mail_brand_label() if rec and hasattr(rec, "_mail_brand_label") else "JUSTECH"),
            )
        brand = rec._mail_brand_label() if hasattr(rec, "_mail_brand_label") else "JUSTECH"
        if request.httprequest.method == "GET":
            csrf = request.csrf_token()
            body = """
            <h1 style="margin:0 0 16px 0;font-size:22px;">¿Desea aprobar esta solicitud?</h1>
            <p style="font-size:13px;color:#6b7280;margin:0 0 12px 0;">Sesión: %(user)s</p>
            %(summary)s
            <form method="post">
              <input type="hidden" name="csrf_token" value="%(csrf)s"/>
              <label style="display:block;margin-bottom:6px;font-weight:600;">Comentario del aprobador</label>
              <textarea name="approver_note" rows="3"
                style="width:100%%;box-sizing:border-box;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-family:inherit;margin-bottom:16px;"
                placeholder="Opcional"></textarea>
              <button type="submit" style="background:#15803d;color:#fff;border:0;padding:14px 24px;border-radius:8px;font-weight:700;font-size:15px;cursor:pointer;width:100%%;max-width:280px;">
                APROBAR SOLICITUD
              </button>
            </form>
            """ % {
                "summary": _summary_block(rec),
                "csrf": _esc(csrf),
                "user": _esc(request.env.user.name),
            }
            return _page(_("Aprobar"), body, brand=brand)
        # POST only — never auto-approve on GET/login return
        note = (post.get("approver_note") or "").strip() or None
        try:
            rec.with_user(request.env.user).with_context(
                justech_approval_token=token
            ).action_approve(note=note, token_flow=True)
        except AccessError as exc:
            return _forbidden_page(str(exc), brand=brand)
        except UserError as exc:
            return _page(_("No se pudo aprobar"), "<p>%s</p>" % _esc(str(exc)), 400, brand=brand)
        return _page(
            _("Aprobación registrada"),
            "<h1 style='margin:0 0 8px 0;font-size:22px;color:#15803d;'>APROBACIÓN REGISTRADA</h1>"
            "<p>%s</p>" % _esc(rec.document_name or rec.display_name),
            brand=brand,
        )

    @http.route(
        "/justech/approval/<string:token>/reject",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        csrf=True,
    )
    def reject(self, token, **post):
        self._ensure_authenticated()
        rec, error = self._request_or_error(token)
        if error:
            return _page(
                _("Solicitud no válida"),
                "<p>%s</p>" % _esc(error),
                status=400,
                brand=(rec._mail_brand_label() if rec and hasattr(rec, "_mail_brand_label") else "JUSTECH"),
            )
        brand = rec._mail_brand_label() if hasattr(rec, "_mail_brand_label") else "JUSTECH"
        if request.httprequest.method == "GET":
            csrf = request.csrf_token()
            body = """
            <h1 style="margin:0 0 16px 0;font-size:22px;">Rechazar solicitud</h1>
            <p style="font-size:13px;color:#6b7280;margin:0 0 12px 0;">Sesión: %(user)s</p>
            %(summary)s
            <form method="post">
              <input type="hidden" name="csrf_token" value="%(csrf)s"/>
              <label style="display:block;margin-bottom:6px;font-weight:600;">Motivo del rechazo *</label>
              <textarea name="reason" required="required" rows="4"
                style="width:100%%;box-sizing:border-box;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-family:inherit;"></textarea>
              <p style="margin-top:16px;">
                <button type="submit" style="background:#b91c1c;color:#fff;border:0;padding:14px 24px;border-radius:8px;font-weight:700;font-size:15px;cursor:pointer;width:100%%;max-width:280px;">
                  RECHAZAR SOLICITUD
                </button>
              </p>
            </form>
            """ % {
                "summary": _summary_block(rec),
                "csrf": _esc(csrf),
                "user": _esc(request.env.user.name),
            }
            return _page(_("Rechazar"), body, brand=brand)
        reason = (post.get("reason") or "").strip()
        if not reason:
            return _page(
                _("Motivo requerido"),
                "<p>Debe indicar el motivo del rechazo.</p>",
                400,
                brand=brand,
            )
        try:
            rec.with_user(request.env.user).with_context(
                justech_approval_token=token
            ).action_reject(note=reason, token_flow=True)
        except AccessError as exc:
            return _forbidden_page(str(exc), brand=brand)
        except UserError as exc:
            return _page(_("No se pudo rechazar"), "<p>%s</p>" % _esc(str(exc)), 400, brand=brand)
        return _page(
            _("Rechazo registrado"),
            "<h1 style='margin:0 0 8px 0;font-size:22px;color:#b91c1c;'>RECHAZO REGISTRADO</h1>"
            "<p>%s</p><p>%s</p>"
            % (_esc(rec.document_name or rec.display_name), _esc(reason)),
            brand=brand,
        )


# ---------------------------------------------------------------------------
# CSRF is validated BEFORE auth in HttpDispatcher. On approval routes a stale
# or missing session yields BadRequest("Session expired (invalid CSRF token)")
# instead of login. Convert that into a login redirect (CSRF stays enabled).
# ---------------------------------------------------------------------------
_original_http_handle_error = http.HttpDispatcher.handle_error


def _justech_approval_handle_error(self, exc):
    try:
        path = (self.request.httprequest.path or "") if self.request else ""
    except Exception:  # noqa: BLE001
        path = ""
    if path.startswith("/justech/approval/") and isinstance(exc, BadRequest):
        desc = str(getattr(exc, "description", "") or exc)
        if "CSRF" in desc or "Session expired" in desc:
            _logger.info(
                "Approval CSRF/session miss on %s → login redirect (CSRF still enabled)",
                path,
            )
            try:
                session = self.request.session
                if session.uid is not None:
                    session.logout(keep_db=True)
            except Exception:  # noqa: BLE001
                pass
            safe = safe_approval_redirect_path(path) or "/odoo"
            return self.request.redirect_query(
                "/web/login",
                {"redirect": safe, "justech_approval_session": "1"},
            )
    if path.startswith("/justech/approval/") and isinstance(exc, SessionExpiredException):
        safe = safe_approval_redirect_path(path) or "/odoo"
        session = self.request.session
        was_connected = session.uid is not None
        session.logout(keep_db=True)
        response = self.request.redirect_query(
            "/web/login",
            {"redirect": safe, "justech_approval_session": "1"},
        )
        if was_connected:
            try:
                from odoo.http import root, get_session_max_inactivity

                root.session_store.rotate(session, self.request.env)
                response.set_cookie(
                    "session_id",
                    session.sid,
                    max_age=get_session_max_inactivity(self.request.env),
                    httponly=True,
                )
            except Exception:  # noqa: BLE001
                _logger.debug("session rotate after approval expiry failed", exc_info=True)
        return response
    return _original_http_handle_error(self, exc)


http.HttpDispatcher.handle_error = _justech_approval_handle_error
