from odoo import models


def _dx_grant_internal_product_create(env):
    """Every internal user can create products. Not Settings / Administrator."""
    user = env.ref("base.group_user", raise_if_not_found=False)
    manager = env.ref("product.group_product_manager", raise_if_not_found=False)
    if not user or not manager:
        return
    if manager not in user.implied_ids:
        user.sudo().write({"implied_ids": [(4, manager.id)]})


class ResGroups(models.Model):
    _inherit = "res.groups"

    def _register_hook(self):
        super()._register_hook()
        _dx_grant_internal_product_create(self.env)
