# -*- coding: utf-8 -*-
"""Hotfix reportes Justech: desactivar Studio destructivo en address_layout.

Identifica la vista por key estable (no por ID numérico), valida inherit_id y
firma del arch destructivo, y la desactiva de forma idempotente.

Rollback:
  UPDATE ir_ui_view SET active = true
  WHERE key = 'web_studio.report_editor_customization_diff.view._web.address_layout';
"""
import logging

_logger = logging.getLogger(__name__)

STUDIO_ADDRESS_KEY = (
    "web_studio.report_editor_customization_diff.view._web.address_layout"
)
EXPECTED_INHERIT_KEY = "web.address_layout"
# Markers from Studio arch (xpath uses [@name='...'] with single quotes).
DESTRUCTIVE_MARKERS = (
    "information_block",
    "name='address'",
    'position="replace"',
    "<br/>",
)


def _arch_text(arch_db):
    if arch_db is None:
        return ""
    if isinstance(arch_db, dict):
        return " ".join(str(v) for v in arch_db.values())
    return str(arch_db)


def _is_destructive_studio_address_view(view, inherit_view):
    if not view or not inherit_view:
        return False
    if (view.key or "") != STUDIO_ADDRESS_KEY:
        return False
    if (inherit_view.key or "") != EXPECTED_INHERIT_KEY:
        return False
    arch = _arch_text(view.arch_db)
    return all(marker in arch for marker in DESTRUCTIVE_MARKERS)


def migrate(cr, version):
    from odoo import api, fields

    env = api.Environment(cr, 1, {})
    View = env["ir.ui.view"].sudo()
    views = View.search([("key", "=", STUDIO_ADDRESS_KEY)])
    if not views:
        _logger.info(
            "justech_l10n_do_ncf 19.0.2.6.0: Studio key %s not found; skip",
            STUDIO_ADDRESS_KEY,
        )
        return

    deactivated = 0
    skipped = 0
    for view in views:
        inherit = view.inherit_id
        if not _is_destructive_studio_address_view(view, inherit):
            _logger.warning(
                "justech_l10n_do_ncf 19.0.2.6.0: view id=%s key=%s did not match "
                "destructive Studio address fingerprint; left untouched (active=%s)",
                view.id,
                view.key,
                view.active,
            )
            skipped += 1
            continue
        if not view.active:
            _logger.info(
                "justech_l10n_do_ncf 19.0.2.6.0: view id=%s already inactive (noop)",
                view.id,
            )
            skipped += 1
            continue
        view.write({"active": False})
        deactivated += 1
        _logger.info(
            "justech_l10n_do_ncf 19.0.2.6.0 AUDIT: deactivated Studio view "
            "id=%s key=%s xmlids=%s inherit_key=%s at=%s",
            view.id,
            view.key,
            view.get_external_id().get(view.id),
            inherit.key,
            fields.Datetime.now(),
        )

    env["ir.config_parameter"].sudo().set_param(
        "justech_l10n_do_ncf.report_hotfix_19_0_2_6_0",
        "studio_address=%s deactivated=%s skipped=%s"
        % (STUDIO_ADDRESS_KEY, deactivated, skipped),
    )
    _logger.info(
        "justech_l10n_do_ncf 19.0.2.6.0: studio address hotfix done "
        "(deactivated=%s skipped=%s)",
        deactivated,
        skipped,
    )
