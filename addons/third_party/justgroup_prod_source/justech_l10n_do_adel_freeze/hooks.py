# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def freeze_adel_journals(env):
    """Disable LATAM documents on journals of Justech-fiscal companies."""
    Journal = env["account.journal"].sudo()
    companies = env["res.company"].sudo().search(
        [("justech_do_fiscal_enabled", "=", True)]
    )
    journals = Journal.search(
        [
            ("company_id", "in", companies.ids),
            ("l10n_latam_use_documents", "=", True),
        ]
    )
    if journals:
        journals.write({"l10n_latam_use_documents": False})
        _logger.info(
            "justech_l10n_do_adel_freeze: disabled l10n_latam_use_documents on %s journals",
            len(journals),
        )
    return len(journals)


def post_init_hook(env):
    freeze_adel_journals(env)
