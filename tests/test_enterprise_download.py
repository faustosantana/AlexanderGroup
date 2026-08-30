"""Descarga oficial odoo.com (sin red): URLs, magia .deb y rechazo de HTML."""

from __future__ import annotations

from email.message import EmailMessage

from tools.enterprise_download import (
    CHECK_ENDPOINT,
    PLATFORM_VERSION,
    THANKS_ENDPOINT,
    EnterpriseDownloadError,
    download_official_deb,
    filename_from_headers,
    looks_like_deb,
    looks_like_html,
    thanks_download_url,
)


def test_official_endpoints() -> None:
    assert CHECK_ENDPOINT == "https://www.odoo.com/download/check_subscription"
    assert THANKS_ENDPOINT == "https://www.odoo.com/thanks/download"
    assert PLATFORM_VERSION == "deb_19e"
    url = thanks_download_url("MUNITTEST")
    assert "platform_version=deb_19e" in url
    assert url.startswith(THANKS_ENDPOINT)
    assert "MUNITTEST" in url


def test_rejects_html_and_accepts_deb_magic() -> None:
    assert looks_like_html(b"<!DOCTYPE html><html>")
    assert looks_like_html(b"<html lang='en'>")
    assert not looks_like_html(b"!<arch>\ndebian-binary")
    assert looks_like_deb(b"!<arch>\n")
    assert not looks_like_deb(b"<!DOCTYPE html>")


def test_filename_from_content_disposition() -> None:
    headers = EmailMessage()
    headers["Content-Disposition"] = (
        'attachment; filename="odoo_19.0+e.20260829_all.deb"'
    )
    assert filename_from_headers(headers) == "odoo_19.0+e.20260829_all.deb"


class _Resp:
    def __init__(self, body: bytes, url: str, headers: EmailMessage, status: int = 200):
        self.status = status
        self._body = body
        self._url = url
        self.headers = headers

    def read(self, n: int = -1) -> bytes:
        return self._body if n < 0 else self._body[:n]

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Opener:
    def __init__(self, check_result: str, download_body: bytes, content_type: str):
        self.check_result = check_result
        self.download_body = download_body
        self.content_type = content_type

    def open(self, req, timeout=None):
        url = req.full_url
        if url.endswith("/download/check_subscription"):
            import json

            payload = json.dumps(
                {"jsonrpc": "2.0", "id": 1, "result": self.check_result}
            ).encode()
            headers = EmailMessage()
            headers["Content-Type"] = "application/json"
            return _Resp(payload, url, headers)
        headers = EmailMessage()
        headers["Content-Type"] = self.content_type
        headers["Content-Disposition"] = (
            'attachment; filename="odoo_19.0+e.20260829_all.deb"'
        )
        return _Resp(self.download_body, url, headers)


def test_download_rejects_html_payload(tmp_path) -> None:
    opener = _Opener("success", b"<!DOCTYPE html><html>login</html>", "text/html")
    try:
        download_official_deb("MUNITTEST", tmp_path, opener=opener)
    except EnterpriseDownloadError as exc:
        assert "HTML" in str(exc)
        return
    raise AssertionError("debía rechazar HTML")


def test_download_writes_deb(tmp_path) -> None:
    body = b"!<arch>\n" + b"0" * 64
    opener = _Opener("success", body, "application/vnd.debian.binary-package")
    dest = download_official_deb("MUNITTEST", tmp_path, opener=opener)
    assert dest.name == "odoo_19.0+e.20260829_all.deb"
    assert dest.read_bytes() == body


def test_download_rejects_invalid_contract(tmp_path) -> None:
    opener = _Opener("oe_download_invalid_code", b"", "text/html")
    try:
        download_official_deb("MUNITTEST", tmp_path, opener=opener)
    except EnterpriseDownloadError as exc:
        assert "oe_download_invalid_code" in str(exc)
        return
    raise AssertionError("debía rechazar contrato inválido")
