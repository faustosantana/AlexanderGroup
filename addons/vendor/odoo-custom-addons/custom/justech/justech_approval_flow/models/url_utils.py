# -*- coding: utf-8 -*-

from urllib.parse import urlparse, urlunparse

from odoo.exceptions import ValidationError
from odoo.tools.translate import _

BLOCKED_SCHEMES = frozenset({"javascript", "file", "data", "vbscript"})
ALLOWED_SCHEMES = frozenset({"https"})
ALLOWED_DOCUMENT_MODELS = frozenset({"sale.order", "purchase.order", "account.move"})
PROD_PUBLIC_HOSTS = frozenset({"justgroup.app", "www.justgroup.app"})


def host_of(url):
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://%s" % raw
    return (urlparse(raw).netloc or "").lower()


def is_cross_environment(public_url, web_base_url):
    """True when public approval host differs from this database's web.base.url host."""
    public_host = host_of(public_url)
    web_host = host_of(web_base_url)
    if not public_host or not web_host:
        return False
    return public_host != web_host


def align_public_url_with_web_base(public_url, web_base_url):
    """Keep explicit public URL unless it would send tokens to another environment."""
    web = (web_base_url or "").strip()
    public = (public_url or "").strip()
    if is_cross_environment(public, web):
        return web.rstrip("/")
    if public:
        return public.rstrip("/")
    return web.rstrip("/") if web else ""


def normalize_public_base_url(url):
    """Return a safe HTTPS base URL without trailing slash."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        prefix = raw.split(":", 1)[0].lower()
        if prefix in BLOCKED_SCHEMES:
            raise ValidationError(_("Esquema de URL no permitido: %s") % prefix)
        raw = "https://%s" % raw
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES:
        raise ValidationError(_("Esquema de URL no permitido: %s") % scheme)
    if scheme not in ALLOWED_SCHEMES:
        raise ValidationError(_("La URL pública de aprobaciones debe usar HTTPS."))
    if not parsed.netloc:
        raise ValidationError(_("La URL pública de aprobaciones no es válida."))
    path = (parsed.path or "").rstrip("/")
    return urlunparse((scheme, parsed.netloc.lower(), path, "", "", ""))


def join_public_url(base_url, *parts):
    """Join base URL with path segments without double slashes."""
    base = normalize_public_base_url(base_url)
    segments = [str(p).strip("/") for p in parts if p]
    if not segments:
        return base
    return "%s/%s" % (base, "/".join(segments))
