"""Keep the Doralex app catalog after a directed -u."""

from odoo import models


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _register_hook(self):
        super()._register_hook()
        margin = self.sudo().search(
            [("name", "=", "justech_purchase_sale_margin_control")], limit=1
        )
        if not margin or not margin.application:
            return
        from odoo.addons.justech_alexander_ux.hooks import (
            _apply_catalog,
            hide_margin_control,
        )

        _apply_catalog(self.env)
        hide_margin_control(self.env)
