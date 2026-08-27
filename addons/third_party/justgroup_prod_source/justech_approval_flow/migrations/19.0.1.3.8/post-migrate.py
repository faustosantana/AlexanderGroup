# -*- coding: utf-8 -*-
"""19.0.1.3.8 — Recover invalidated PO approval; PDF/send gates (log-only migrate)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "justech_approval_flow 19.0.1.3.8: "
        "re-request button for to approve+invalidated; new request/token; "
        "friendly token message; final PO PDF gate; vendor send until approved."
    )
