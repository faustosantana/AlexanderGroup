from odoo import api, models
from odoo.exceptions import ValidationError

from .account_tax import _CROSS_COMPANY_TAX_MSG
from .product_template import _command_tax_ids


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _dx_document_company(self):
        self.ensure_one()
        return self.company_id or self.order_id.company_id or self.env.company

    def _dx_filter_tax_vals(self, vals):
        if "tax_ids" not in vals:
            return vals
        company = None
        if vals.get("company_id"):
            company = self.env["res.company"].browse(vals["company_id"])
        elif vals.get("order_id"):
            company = self.env["purchase.order"].browse(vals["order_id"]).company_id
        elif self:
            company = self[:1]._dx_document_company()
        company = company or self.env.company
        taxes = (
            self.env["account.tax"].sudo().browse(_command_tax_ids(vals.get("tax_ids")))
        )
        vals = dict(vals)
        vals["tax_ids"] = [(6, 0, taxes._filter_taxes_by_company(company).ids)]
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._dx_filter_tax_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if "tax_ids" in vals:
            vals = self._dx_filter_tax_vals(vals)
        return super().write(vals)

    def _compute_tax_id(self):
        for line in self:
            product = line.product_id
            if product and hasattr(product, "_dx_taxes_for_company"):
                product._dx_taxes_for_company(
                    line.company_id or line.order_id.company_id,
                    field_name="supplier_taxes_id",
                )
        return super()._compute_tax_id()

    @api.constrains("tax_ids", "company_id", "order_id")
    def _dx_check_purchase_tax_company(self):
        for line in self:
            if line.display_type or not line.tax_ids:
                continue
            company = line.company_id or line.order_id.company_id
            bad = line.sudo().tax_ids.filtered(
                lambda tax: tax.company_id and tax.company_id != company
            )
            if not bad:
                continue
            if line.order_id.state in ("draft", "sent", "to approve"):
                if hasattr(line, "_compute_tax_id"):
                    line._compute_tax_id()
                bad = line.sudo().tax_ids.filtered(
                    lambda tax: tax.company_id and tax.company_id != company
                )
            if bad:
                raise ValidationError(_CROSS_COMPANY_TAX_MSG)
