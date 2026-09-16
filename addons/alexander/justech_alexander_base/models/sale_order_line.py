from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _dx_description_for_product(self):
        self.ensure_one()
        product = self.product_id
        if not product:
            return self.name or ""
        getter = getattr(product, "get_product_multiline_description_sale", None)
        if getter:
            return getter()
        tmpl = product.product_tmpl_id
        desc = (tmpl.description_sale or "").strip()
        name = product.display_name or tmpl.name or ""
        if desc:
            return "%s\n%s" % (name, desc)
        return name

    def _dx_refresh_name_from_product(self):
        for line in self:
            if line.display_type or not line.product_id:
                continue
            expected = line._dx_description_for_product()
            if line.name != expected:
                line.name = expected

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        to_fix = lines.filtered(
            lambda l: not l.display_type and l.product_id and not (l.name or "").strip()
        )
        if to_fix:
            to_fix._dx_refresh_name_from_product()
        return lines

    def write(self, vals):
        old_products = {}
        if "product_id" in vals:
            old_products = {line.id: line.product_id.id for line in self}
        result = super().write(vals)
        if "product_id" in vals:
            changed = self.filtered(
                lambda l: not l.display_type
                and l.product_id
                and old_products.get(l.id) != l.product_id.id
            )
            if changed:
                changed._dx_refresh_name_from_product()
        return result
