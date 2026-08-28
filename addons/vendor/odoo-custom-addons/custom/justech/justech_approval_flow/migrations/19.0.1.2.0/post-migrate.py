# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rule = env["justech.approval.user.rule"].sudo()
    for company in env["res.company"].search([]):
        for user in company.justech_approval_user_ids:
            if Rule.search([("user_id", "=", user.id)], limit=1):
                continue
            Rule.create(
                {
                    "user_id": user.id,
                    "active": True,
                    "approve_sale": True,
                    "approve_purchase": True,
                    "approve_invoice": True,
                    "allow_self_approval": user.has_group(
                        "justech_approval_flow.group_self_approve"
                    ),
                }
            )
    icp = env["ir.config_parameter"].sudo()
    if not icp.get_param("justech.approval.public.base.url"):
        icp.set_param("justech.approval.public.base.url", "https://justgroup.app")
