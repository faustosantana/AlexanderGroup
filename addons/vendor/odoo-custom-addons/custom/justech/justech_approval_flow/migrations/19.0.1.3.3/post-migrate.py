# -*- coding: utf-8 -*-
"""Normalize approver rules by (user, company) and remove exact duplicates."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["justech.approval.user.rule"].normalize_company_rules(strict_conflict=True)
