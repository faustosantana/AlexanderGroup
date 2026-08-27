# -*- coding: utf-8 -*-
"""Post-migrate 19.0.1.6.10 — configs pendientes + quarantine UAT en producción."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if (
        "justech.do.withholding.catalog" not in env.registry
        or "justech.do.withholding.company.config" not in env.registry
    ):
        _logger.warning("post-migrate 19.0.1.6.10: models missing")
        return
    Catalog = env["justech.do.withholding.catalog"]
    Config = env["justech.do.withholding.company.config"]

    # No incluir UAT en sync de producción.
    companies = env["res.company"].search([])
    do_company = companies.filtered(lambda c: c.country_id and c.country_id.code == "DO")[:1]
    company = do_company or env.company
    Catalog.with_context(justech_sync_uat_withholdings=False).sync_catalog_from_taxes(company)
    Catalog.ensure_company_configs(companies=companies)

    # Si existiera algún UAT-* (p.ej. copiado), desactivar y no utilizable.
    uat = Catalog.with_context(active_test=False).search([("code", "=like", "UAT-%")])
    if uat:
        uat.write({"active": False, "pending_confirmation": True})
        cfgs = Config.search([("catalog_id", "in", uat.ids)])
        if cfgs:
            cfgs.write({"active_config": False, "account_id": False})
        _logger.warning("post-migrate 19.0.1.6.10: quarantined UAT catalogs: %s", uat.mapped("code"))

    # Garantizar configs sin cuenta permanecen inactivas.
    pending = Config.search([("|", ("account_id", "=", False), ("active_config", "=", True))])
    for cfg in pending:
        if not cfg.account_id and cfg.active_config:
            cfg.write({"active_config": False})

    _logger.info(
        "post-migrate 19.0.1.6.10: catalog=%s configs=%s uat=%s",
        Catalog.with_context(active_test=False).search_count([]),
        Config.search_count([]),
        len(uat),
    )
