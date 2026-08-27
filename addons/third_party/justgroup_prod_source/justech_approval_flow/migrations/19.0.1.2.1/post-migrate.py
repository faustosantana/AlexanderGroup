# -*- coding: utf-8 -*-

from urllib.parse import urlparse

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Realign public approval URL with this database's web.base.url.

    DEV emails must not point at justgroup.app while the request lives in justech_dev.
    PROD keeps https://justgroup.app because that is also web.base.url there.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env["ir.config_parameter"].sudo()
    web = (icp.get_param("web.base.url") or "").strip()
    public = (icp.get_param("justech.approval.public.base.url") or "").strip()

    def host(url):
        raw = (url or "").strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = "https://%s" % raw
        return (urlparse(raw).netloc or "").lower()

    public_host = host(public)
    web_host = host(web)
    aligned = public.rstrip("/") if public else web.rstrip("/")
    if public_host and web_host and public_host != web_host:
        aligned = web.rstrip("/")
    elif not public and web:
        aligned = web.rstrip("/")
    if aligned:
        icp.set_param("justech.approval.public.base.url", aligned)
