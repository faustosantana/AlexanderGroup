# -*- coding: utf-8 -*-
"""19.0.8.29.2 — Shared CxP source domain (posted vendor bills with residual)."""


def open_vendor_bill_domain(company_ids=None):
    """Posted vendor bills/NC with outstanding residual. No auxiliary table."""
    domain = [
        ("move_type", "in", ("in_invoice", "in_refund")),
        ("state", "=", "posted"),
        ("amount_residual", "!=", 0),
    ]
    if company_ids:
        domain.append(("company_id", "in", list(company_ids)))
    return domain
