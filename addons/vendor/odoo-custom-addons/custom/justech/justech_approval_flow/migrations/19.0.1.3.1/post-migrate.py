# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Drop the 19.0.1.3.0 approver-read ACL on justech.approval.user.rule."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    access = env.ref(
        "justech_approval_flow.access_justech_approval_user_rule_read",
        raise_if_not_found=False,
    )
    if access:
        access.unlink()
