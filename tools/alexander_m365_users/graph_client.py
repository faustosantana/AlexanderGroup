"""Cliente Graph con certificado de aplicación. No persiste tokens."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com/%s/oauth2/v2.0/token"


def secrets_dir() -> Path:
    return Path(os.environ.get("DX_MS_GRAPH_DIR") or "/opt/doralex/secrets/microsoft")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def token() -> str:
    d = secrets_dir()
    tenant = (d / "tenant_id").read_text().strip()
    client_id = (d / "client_id").read_text().strip()
    thumb = (d / "thumbprint").read_text().strip().replace(":", "").upper()
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT", "x5t": _b64url(bytes.fromhex(thumb))}
    payload = {
        "aud": LOGIN % tenant,
        "iss": client_id,
        "sub": client_id,
        "jti": str(uuid.uuid4()),
        "nbf": now - 5,
        "exp": now + 540,
    }
    signing = "%s.%s" % (
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(payload, separators=(",", ":")).encode()),
    )
    sig = subprocess.check_output(
        ["openssl", "dgst", "-sha256", "-sign", str(d / "app.key")],
        input=signing.encode(),
    )
    assertion = "%s.%s" % (signing, _b64url(sig))
    body = (
        "client_id=%s&scope=https%%3A%%2F%%2Fgraph.microsoft.com%%2F.default"
        "&grant_type=client_credentials&client_assertion_type="
        "urn%%3Aietf%%3Aparams%%3Aoauth%%3Aclient-assertion-type%%3Ajwt-bearer"
        "&client_assertion=%s" % (client_id, assertion)
    )
    req = urllib.request.Request(
        LOGIN % tenant,
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read())["access_token"]


def call(tok: str, method: str, path: str, payload=None, timeout: int = 60):
    data = None
    headers = {"Authorization": "Bearer " + tok}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        GRAPH + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {"error_text": exc.read().decode("utf-8", "replace")[:1200]}


def get_user(tok: str, upn: str):
    return call(tok, "GET", "/users/%s" % urllib.parse.quote(upn))
