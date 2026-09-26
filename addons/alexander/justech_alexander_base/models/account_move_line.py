from odoo import api, models
from odoo.exceptions import ValidationError

from .account_tax import _CROSS_COMPANY_TAX_MSG
from .product_template import _command_tax_ids


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _dx_document_company(self):
        self.ensure_one()
        return self.company_id or self.move_id.company_id or self.env.company

    def _dx_filter_tax_vals(self, vals):
        if "tax_ids" not in vals:
            return vals
        company = None
        if vals.get("company_id"):
            company = self.env["res.company"].browse(vals["company_id"])
        elif vals.get("move_id"):
            company = self.env["account.move"].browse(vals["move_id"]).company_id
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
        if "tax_ids" not in vals:
            return super().write(vals)
        posted = self.filtered(lambda line: line.move_id.state == "posted")
        drafts = self - posted
        result = True
        if posted:
            posted_vals = {key: item for key, item in vals.items() if key != "tax_ids"}
            if posted_vals:
                result = super(AccountMoveLine, posted).write(posted_vals)
        if drafts:
            result = super(AccountMoveLine, drafts).write(
                self._dx_filter_tax_vals(vals)
            )
        return result

    def _get_computed_taxes(self):
        self.ensure_one()
        product = self.product_id
        if product and hasattr(product, "_dx_taxes_for_company"):
            field_name = (
                "taxes_id"
                if self.move_id.is_sale_document(include_receipts=True)
                else "supplier_taxes_id"
            )
            product._dx_taxes_for_company(
                self.move_id.company_id, field_name=field_name
            )
        return super()._get_computed_taxes()

    @api.constrains("tax_ids", "company_id", "move_id")
    def _dx_check_move_tax_company(self):
        for line in self:
            if line.display_type or not line.tax_ids:
                continue
            if line.move_id.state == "posted":
                continue
            company = line.company_id or line.move_id.company_id
            bad = line.sudo().tax_ids.filtered(
                lambda tax: tax.company_id and tax.company_id != company
            )
            if not bad:
                continue
            if hasattr(line, "_compute_tax_ids"):
                line._compute_tax_ids()
            bad = line.sudo().tax_ids.filtered(
                lambda tax: tax.company_id and tax.company_id != company
            )
            if bad:
                raise ValidationError(_CROSS_COMPANY_TAX_MSG)
