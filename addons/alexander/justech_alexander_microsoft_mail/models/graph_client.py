"""Cliente Microsoft Graph app-only (certificado). Sin secretos en Git ni en logs."""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import time
import uuid
from email.utils import getaddresses, parseaddr
from pathlib import Path

from odoo import models
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.exceptions import UserError

from .catalog import belongs_to_domain, domain_of

_logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
LOGIN_URL_TMPL = "https://login.microsoftonline.com/%s/oauth2/v2.0/token"
DEFAULT_CRED_DIR = "/mnt/ms-graph"
_AUTH_CACHE = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _secrets_dir() -> Path:
    return Path(os.environ.get("DX_MS_GRAPH_DIR") or DEFAULT_CRED_DIR)


def _read_secret_file(name: str) -> str:
    path = _secrets_dir() / name
    if not path.is_file():
        raise UserError("Falta el archivo de credencial Microsoft: %s" % name)
    return path.read_text(encoding="utf-8").strip()


class DxMsGraphClient(models.AbstractModel):
    _name = "dx.ms.graph.client"
    _description = "Cliente Microsoft Graph Doralex"

    def _credentials(self):
        tenant = _read_secret_file("tenant_id")
        client_id = _read_secret_file("client_id")
        thumbprint = _read_secret_file("thumbprint").replace(":", "").upper()
        key_path = _secrets_dir() / "app.key"
        if not key_path.is_file():
            raise UserError("Falta el certificado de aplicación Microsoft.")
        return tenant, client_id, thumbprint, str(key_path)

    def _access_token(self):
        tenant, client_id, thumbprint, key_path = self._credentials()
        cached = _AUTH_CACHE.get(client_id) or {}
        if cached.get("exp", 0) > time.time() + 60:
            return cached["auth"]
        now = int(time.time())
        header = {
            "alg": "RS256",
            "typ": "JWT",
            "x5t": _b64url(bytes.fromhex(thumbprint)),
        }
        payload = {
            "aud": LOGIN_URL_TMPL % tenant,
            "iss": client_id,
            "sub": client_id,
            "jti": str(uuid.uuid4()),
            "nbf": now - 5,
            "exp": now + 9 * 60,
        }
        signing_input = "%s.%s" % (
            _b64url(json.dumps(header, separators=(",", ":")).encode()),
            _b64url(json.dumps(payload, separators=(",", ":")).encode()),
        )
        signature = subprocess.check_output(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input.encode(),
        )
        assertion = "%s.%s" % (signing_input, _b64url(signature))
        body = (
            "client_id=%s&scope=https%%3A%%2F%%2Fgraph.microsoft.com%%2F.default"
            "&grant_type=client_credentials&client_assertion_type="
            "urn%%3Aietf%%3Aparams%%3Aoauth%%3Aclient-assertion-type%%3Ajwt-bearer"
            "&client_assertion=%s" % (client_id, assertion)
        )
        status, data = self._http(
            "POST",
            LOGIN_URL_TMPL % tenant,
            raw_body=body.encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=False,
        )
        auth = (data or {}).get("access_token")
        if status >= 300 or not auth:
            _logger.error("Microsoft login request failed status=%s", status)
            raise UserError("No se pudo autenticar la aplicación Microsoft Graph.")
        _AUTH_CACHE[client_id] = {
            "auth": auth,
            "exp": now + int(data.get("expires_in") or 600),
        }
        return auth

    def _http(
        self,
        method,
        url,
        payload=None,
        raw_body=None,
        headers=None,
        auth=True,
        timeout=45,
        accept=None,
    ):
        import urllib.error
        import urllib.request

        hdrs = {"Accept": accept or "application/json"}
        if headers:
            hdrs.update(headers)
        if auth:
            hdrs["Authorization"] = "Bearer %s" % self._access_token()
        data = raw_body
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype and raw:
                    return resp.status, json.loads(raw.decode("utf-8"))
                return resp.status, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed = {}
            try:
                parsed = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                parsed = {"error_body": raw[:400].decode("utf-8", "replace")}
            if exc.code == 429:
                _logger.warning("Microsoft Graph throttled url=%s", url.split("?")[0])
            else:
                _logger.error(
                    "Microsoft Graph error status=%s url=%s",
                    exc.code,
                    url.split("?")[0],
                )
            return exc.code, parsed

    def configured(self):
        try:
            directory = _secrets_dir()
            return all(
                (directory / name).is_file()
                for name in ("tenant_id", "client_id", "thumbprint", "app.key")
            )
        except Exception:
            return False

    def send_message(
        self,
        mailbox,
        from_addr,
        to_addrs,
        cc_addrs,
        bcc_addrs,
        subject,
        body_html,
        body_text,
        reply_to,
        message_id,
        attachments,
        in_reply_to=None,
    ):
        domain = domain_of(mailbox)
        if not belongs_to_domain(from_addr, domain):
            raise MailDeliveryException(
                "Microsoft Mail",
                "El remitente no pertenece al dominio de la empresa.",
            )
        recipients = lambda addrs: [
            {"emailAddress": {"address": addr}} for addr in addrs if addr
        ]
        message = {
            "subject": subject or "",
            "body": {
                "contentType": "HTML" if body_html else "Text",
                "content": body_html or body_text or "",
            },
            "toRecipients": recipients(to_addrs),
            "ccRecipients": recipients(cc_addrs),
            "bccRecipients": recipients(bcc_addrs),
            "from": {"emailAddress": {"address": from_addr}},
        }
        if reply_to:
            message["replyTo"] = recipients([reply_to])
        if message_id:
            message["internetMessageId"] = message_id
        if in_reply_to:
            message["internetMessageHeaders"] = [
                {"name": "In-Reply-To", "value": in_reply_to}
            ]
        if attachments:
            message["attachments"] = attachments
        status, data = self._http(
            "POST",
            "%s/users/%s/sendMail" % (GRAPH_BASE, mailbox),
            payload={"message": message, "saveToSentItems": True},
        )
        if status not in (202, 200, 204):
            raise MailDeliveryException(
                "Microsoft Mail",
                "Graph Mail.Send rechazó el mensaje (status %s)." % status,
            )
        return message_id or True

    def send_email_message(self, message, mailbox, from_addr):
        raw = message
        get = raw.get
        subject = get("Subject") or ""
        reply_to = parseaddr(get("Reply-To") or "")[1] or from_addr
        message_id = get("Message-Id") or get("Message-ID")
        in_reply_to = get("In-Reply-To")
        to_addrs = [addr for _, addr in getaddresses(raw.get_all("To", []))]
        cc_addrs = [addr for _, addr in getaddresses(raw.get_all("Cc", []))]
        bcc_addrs = [addr for _, addr in getaddresses(raw.get_all("Bcc", []))]
        body_html = ""
        body_text = ""
        attachments = []
        if raw.is_multipart():
            for part in raw.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if ctype == "text/html" and "attachment" not in disp:
                    payload = part.get_payload(decode=True) or b""
                    body_html = payload.decode(
                        part.get_content_charset() or "utf-8", "replace"
                    )
                elif (
                    ctype == "text/plain" and "attachment" not in disp and not body_text
                ):
                    payload = part.get_payload(decode=True) or b""
                    body_text = payload.decode(
                        part.get_content_charset() or "utf-8", "replace"
                    )
                elif part.get_filename() or "attachment" in disp:
                    payload = part.get_payload(decode=True) or b""
                    if len(payload) > 20 * 1024 * 1024:
                        _logger.warning("Skipping oversized Graph attachment")
                        continue
                    attachments.append(
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": part.get_filename() or "adjunto",
                            "contentType": ctype or "application/octet-stream",
                            "contentBytes": base64.b64encode(payload).decode("ascii"),
                        }
                    )
        else:
            payload = raw.get_payload(decode=True) or b""
            text = payload.decode(raw.get_content_charset() or "utf-8", "replace")
            if raw.get_content_type() == "text/html":
                body_html = text
            else:
                body_text = text
        return self.send_message(
            mailbox=mailbox,
            from_addr=from_addr,
            to_addrs=to_addrs,
            cc_addrs=cc_addrs,
            bcc_addrs=bcc_addrs,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            reply_to=reply_to,
            message_id=message_id,
            attachments=attachments,
            in_reply_to=in_reply_to,
        )

    def list_inbox(self, mailbox, top=25):
        import urllib.parse

        qs = urllib.parse.urlencode(
            {
                "$top": str(top),
                "$select": "id,subject,from,receivedDateTime,internetMessageId,isRead,hasAttachments",
                "$orderby": "receivedDateTime desc",
            }
        )
        url = "%s/users/%s/mailFolders/inbox/messages?%s" % (
            GRAPH_BASE,
            urllib.parse.quote(mailbox),
            qs,
        )
        status, data = self._http("GET", url)
        if status != 200:
            _logger.error("Inbox list failed mailbox=%s status=%s", mailbox, status)
            return []
        return data.get("value") or []

    def get_mime(self, mailbox, graph_id):
        import urllib.parse

        url = "%s/users/%s/messages/%s/$value" % (
            GRAPH_BASE,
            urllib.parse.quote(mailbox),
            urllib.parse.quote(graph_id),
        )
        status, data = self._http(
            "GET", url, accept="message/rfc822, application/octet-stream, */*"
        )
        if status != 200:
            return b""
        return data if isinstance(data, (bytes, bytearray)) else b""

    def mark_read(self, mailbox, graph_id):
        import urllib.parse

        url = "%s/users/%s/messages/%s" % (
            GRAPH_BASE,
            urllib.parse.quote(mailbox),
            urllib.parse.quote(graph_id),
        )
        self._http("PATCH", url, payload={"isRead": True})
