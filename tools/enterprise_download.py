"""Descarga oficial Odoo 19 Enterprise (.deb Ubuntu/Debian) desde odoo.com.

Flujo real de https://www.odoo.com/page/download
(Odoo 19 → Ubuntu • Debian → Enterprise, data-platform-version=deb_19e):

1. JSON-RPC POST /download/check_subscription  params={code}
   result: success | oe_download_invalid_code | oe_download_not_allowed
           | oe_download_invalid_status
2. Si success: GET /thanks/download?code=...&platform_version=deb_19e
   (sigue redirects; debe ser un .deb, no HTML).

No imprime el código. No usa nightly ni Community como resultado.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.enterprise_source import is_official_enterprise_package_name
except ImportError:  # ejecución desde /opt/doralex/tools
    from enterprise_source import is_official_enterprise_package_name  # type: ignore

CHECK_ENDPOINT = "https://www.odoo.com/download/check_subscription"
THANKS_ENDPOINT = "https://www.odoo.com/thanks/download"
PLATFORM_VERSION = "deb_19e"
USER_AGENT = "Doralex-Enterprise-Staging/1.0 (+official odoo.com download)"


class EnterpriseDownloadError(RuntimeError):
    """Fallo documentado de la descarga oficial (sin secretos)."""


@dataclass(frozen=True)
class DownloadProbe:
    http_status: int
    final_url: str
    auth_required: bool
    subscription_required: bool
    download_endpoint: str
    reason: str
    content_type: str = ""
    body_kind: str = ""


def thanks_download_url(code: str) -> str:
    q = urllib.parse.urlencode({"code": code, "platform_version": PLATFORM_VERSION})
    return f"{THANKS_ENDPOINT}?{q}"


def looks_like_html(data: bytes) -> bool:
    head = data.lstrip()[:200].lower()
    return (
        head.startswith(b"<!doctype")
        or head.startswith(b"<html")
        or b"<html" in head[:80]
    )


def looks_like_deb(data: bytes) -> bool:
    return data.startswith(b"!<arch>")


def filename_from_headers(headers, fallback: str = "odoo_19.0+e.latest_all.deb") -> str:
    disp = (
        headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    )
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disp, flags=re.I)
    if match:
        return Path(match.group(1).strip()).name
    return fallback


def jsonrpc_check_subscription(code: str, opener=None) -> tuple[int, str]:
    """Devuelve (http_status, result_or_error_token). Nunca incluye el código."""
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": "call", "params": {"code": code}, "id": 1}
    ).encode("utf-8")
    req = urllib.request.Request(
        CHECK_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    handler = opener or urllib.request.build_opener()
    try:
        with handler.open(req, timeout=45) as resp:
            status = getattr(resp, "status", 200)
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, f"http_{exc.code}"
    result = body.get("result")
    if isinstance(result, str) and result:
        return status, result
    if body.get("error"):
        return status, "server_error"
    return status, "unknown"


def probe_without_code(opener=None) -> DownloadProbe:
    """Inspección sin contrato: documenta el bloqueo real."""
    status, result = jsonrpc_check_subscription("", opener=opener)
    thanks = f"{THANKS_ENDPOINT}?platform_version={PLATFORM_VERSION}"
    handler = opener or urllib.request.build_opener()
    content_type = ""
    body_kind = ""
    final_url = thanks
    thanks_status = 0
    try:
        req = urllib.request.Request(
            thanks, headers={"User-Agent": USER_AGENT}, method="GET"
        )
        with handler.open(req, timeout=45) as resp:
            thanks_status = getattr(resp, "status", 200)
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            chunk = resp.read(64)
            if looks_like_deb(chunk):
                body_kind = "deb"
            elif looks_like_html(chunk):
                body_kind = "html"
            else:
                body_kind = "other"
    except urllib.error.HTTPError as exc:
        thanks_status = exc.code
        final_url = exc.geturl() if hasattr(exc, "geturl") else thanks
    return DownloadProbe(
        http_status=status,
        final_url=final_url,
        auth_required=False,
        subscription_required=True,
        download_endpoint=CHECK_ENDPOINT,
        reason=result,
        content_type=content_type or f"thanks_http={thanks_status}",
        body_kind=body_kind,
    )


def download_official_deb(code: str, dest_dir: Path, opener=None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    status, result = jsonrpc_check_subscription(code, opener=opener)
    if result != "success":
        raise EnterpriseDownloadError(
            f"check_subscription http={status} result={result}"
        )
    url = thanks_download_url(code)
    handler = opener or urllib.request.build_opener(
        urllib.request.HTTPRedirectHandler()
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    with handler.open(req, timeout=180) as resp:
        final_url = resp.geturl()
        headers = resp.headers
        data = resp.read()
    if looks_like_html(data) or "html" in (headers.get("Content-Type") or "").lower():
        raise EnterpriseDownloadError(
            f"thanks/download devolvió HTML en vez de .deb final_url={final_url}"
        )
    if not looks_like_deb(data):
        raise EnterpriseDownloadError(
            f"gracias/download no es un .deb (magic incorrecto) final_url={final_url}"
        )
    name = filename_from_headers(headers)
    if not is_official_enterprise_package_name(name):
        # Algunos CDNs no mandan filename; aceptar solo si el contenido es .deb
        # y forzar el nombre oficial esperado.
        name = "odoo_19.0+e.latest_all.deb"
    dest = dest_dir / name
    dest.write_bytes(data)
    return dest
