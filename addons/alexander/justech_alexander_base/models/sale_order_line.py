from odoo import api, models
from odoo.exceptions import ValidationError

from .account_tax import _CROSS_COMPANY_TAX_MSG


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
        for vals in vals_list:
            if "tax_ids" in vals and (vals.get("company_id") or vals.get("order_id")):
                company = None
                if vals.get("company_id"):
                    company = self.env["res.company"].browse(vals["company_id"])
                elif vals.get("order_id"):
                    company = self.env["sale.order"].browse(vals["order_id"]).company_id
                if company:
                    from .product_template import _command_tax_ids

                    taxes = (
                        self.env["account.tax"]
                        .sudo()
                        .browse(_command_tax_ids(vals.get("tax_ids")))
                    )
                    vals["tax_ids"] = [
                        (6, 0, taxes._filter_taxes_by_company(company).ids)
                    ]
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
        if "tax_ids" in vals:
            vals = dict(vals)
            vals["tax_ids"] = self._dx_tax_commands_for_company(vals.get("tax_ids"))
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

    def _dx_document_company(self):
        self.ensure_one()
        return self.company_id or self.order_id.company_id or self.env.company

    def _dx_tax_commands_for_company(self, value):
        from .product_template import _command_tax_ids

        company = self[:1]._dx_document_company() if self else self.env.company
        taxes = self.env["account.tax"].sudo().browse(_command_tax_ids(value))
        taxes = taxes._filter_taxes_by_company(company)
        return [(6, 0, taxes.ids)]

    def _compute_tax_ids(self):
        for line in self:
            product = line.product_id
            if product and hasattr(product, "_dx_taxes_for_company"):
                company = line.company_id or line.order_id.company_id
                product._dx_taxes_for_company(company)
        return super()._compute_tax_ids()

    @api.constrains("tax_ids", "company_id", "order_id")
    def _dx_check_sale_tax_company(self):
        for line in self:
            if line.display_type or not line.tax_ids:
                continue
            company = line.company_id or line.order_id.company_id
            bad = line.sudo().tax_ids.filtered(
                lambda tax: tax.company_id and tax.company_id != company
            )
            if not bad:
                continue
            if line.order_id.state in ("draft", "sent"):
                line._compute_tax_ids()
                bad = line.sudo().tax_ids.filtered(
                    lambda tax: tax.company_id and tax.company_id != company
                )
            if bad:
                raise ValidationError(_CROSS_COMPANY_TAX_MSG)
