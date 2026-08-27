# -*- coding: utf-8 -*-
"""Remove leftover approver-read ACL on justech.approval.user.rule.

Runs on 19.0.1.3.1 → 19.0.1.3.2 so same-version 1.3.1 migrations are not
relied upon. Idempotent. Does not touch commercial documents or flags.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    access = env.ref(
        "justech_approval_flow.access_justech_approval_user_rule_read",
        raise_if_not_found=False,
    )
    if access:
        access.unlink()
    leftover = env["ir.model.access"].sudo().search(
        [
            ("name", "=", "justech.approval.user.rule read"),
            ("model_id.model", "=", "justech.approval.user.rule"),
        ]
    )
    if leftover:
        leftover.unlink()
