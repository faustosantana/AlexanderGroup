# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.justech_approval_flow.hooks import post_init_hook

    post_init_hook(env)
    template = env.ref(
        "justech_approval_flow.mail_template_approval_request",
        raise_if_not_found=False,
    )
    if template and template.use_default_to:
        template.use_default_to = False
