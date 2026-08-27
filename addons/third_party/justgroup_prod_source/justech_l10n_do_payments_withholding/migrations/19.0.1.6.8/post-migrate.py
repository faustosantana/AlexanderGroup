# -*- coding: utf-8 -*-
"""Post-migrate 19.0.1.6.8 — materializar catálogo + configs por empresa."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    # Prefer env[] — env.get can miss models mid-upgrade on some Odoo builds.
    if "justech.do.withholding.catalog" not in env.registry:
        _logger.warning("post-migrate 19.0.1.6.8: catalog model missing")
        return
    Catalog = env["justech.do.withholding.catalog"]
    companies = env["res.company"].search([])
    do_company = companies.filtered(lambda c: c.country_id and c.country_id.code == "DO")[:1]
    company = do_company or env.company
    try:
        Catalog.sync_catalog_from_taxes(company)
        Catalog.ensure_company_configs(companies=companies)
        _logger.info(
            "post-migrate 19.0.1.6.8: catalog=%s configs=%s",
            Catalog.search_count([]),
            env["justech.do.withholding.company.config"].search_count([]),
        )
    except Exception:
        _logger.exception("post-migrate 19.0.1.6.8 sync failed")
        raise
