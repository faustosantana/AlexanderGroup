from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.fields import Command

from .account_tax import _CROSS_COMPANY_TAX_MSG
from .catalog import operational_companies

_TAX_M2M = ("taxes_id", "supplier_taxes_id")


def _command_tax_ids(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], int):
        return list(value)
    ids = []
    for item in value or []:
        if not item:
            continue
        if isinstance(item, int):
            ids.append(item)
            continue
        cmd = item[0]
        if cmd == Command.SET and len(item) > 2:
            ids.extend(item[2] or [])
        elif cmd in (Command.LINK, Command.CREATE) and len(item) > 1 and item[1]:
            ids.append(item[1])
        elif cmd == 6 and len(item) > 2:
            ids.extend(item[2] or [])
        elif cmd == 4 and len(item) > 1 and item[1]:
            ids.append(item[1])
    return ids


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _dx_taxes_for_company(self, company, field_name="taxes_id"):
        """Native per-company taxes for a shared product. Never duplicates products."""
        self.ensure_one()
        company = company or self.env.company
        taxes = self.sudo()[field_name]
        return taxes._filter_taxes_by_company(company)

    def _construct_tax_string(self, price):
        return super(
            ProductTemplate, self.sudo().with_company(self.env.company)
        )._construct_tax_string(price)

    def _dx_equivalent_tax(self, tax, target_company):
        if not tax or not target_company:
            return self.env["account.tax"]
        if tax.company_id == target_company:
            return tax
        matches = (
            self.env["account.tax"]
            .sudo()
            .search(
                [
                    ("company_id", "=", target_company.id),
                    ("type_tax_use", "=", tax.type_tax_use),
                    ("amount_type", "=", tax.amount_type),
                    ("amount", "=", tax.amount),
                    ("active", "=", True),
                ]
            )
        )
        named = matches.filtered(lambda candidate: candidate.name == tax.name)
        return named[:1] or matches[:1]

    def _dx_mirror_shared_product_taxes(self, field_name, incoming):
        """Keep one shared product; attach the equivalent tax of every operating company."""
        self.ensure_one()
        if self.company_id or not incoming:
            return incoming
        operational = operational_companies(self.env)
        mirrored = incoming
        for tax in incoming:
            for company in operational:
                if tax.company_id == company:
                    continue
                equivalent = self._dx_equivalent_tax(tax, company)
                mirrored |= equivalent
        return mirrored

    def _dx_write_company_taxes(self, field_name, value):
        incoming = self.env["account.tax"].sudo().browse(_command_tax_ids(value))
        incoming = incoming.exists()
        allowed = self.env.companies
        incoming_ok = incoming.filtered(lambda tax: tax.company_id in allowed)
        incoming_bad = incoming - incoming_ok
        if incoming_bad:
            raise ValidationError(_CROSS_COMPANY_TAX_MSG)
        for rec in self:
            existing = rec.sudo()[field_name]
            keep = existing.filtered(lambda tax: tax.company_id not in allowed)
            merged = keep | incoming_ok
            if not rec.company_id:
                merged = rec._dx_mirror_shared_product_taxes(field_name, merged)
            elif rec.company_id:
                merged = merged.filtered(lambda tax: tax.company_id == rec.company_id)
            if merged != existing:
                rec.sudo()[field_name] = merged

    @api.model_create_multi
    def create(self, vals_list):
        extracted = []
        for vals in vals_list:
            extracted.append(
                {name: vals.pop(name) for name in _TAX_M2M if name in vals}
            )
        records = super().create(vals_list)
        for rec, tax_vals in zip(records, extracted):
            for field_name, value in tax_vals.items():
                rec._dx_write_company_taxes(field_name, value)
            if not tax_vals and not rec.company_id:
                rec._dx_mirror_defaults_for_shared()
        return records

    def write(self, vals):
        tax_vals = {name: vals.pop(name) for name in _TAX_M2M if name in vals}
        result = super().write(vals)
        for field_name, value in tax_vals.items():
            self._dx_write_company_taxes(field_name, value)
        return result

    def _dx_mirror_defaults_for_shared(self):
        """New shared products created in one company get the sibling company taxes."""
        operational = operational_companies(self.env)
        for rec in self.filtered(lambda product: not product.company_id):
            for field_name, company_field in (
                ("taxes_id", "account_sale_tax_id"),
                ("supplier_taxes_id", "account_purchase_tax_id"),
            ):
                current = rec.sudo()[field_name]
                if not current:
                    defaults = operational.mapped(company_field)
                    if defaults:
                        rec.sudo()[field_name] = defaults
                    continue
                rec.sudo()[field_name] = rec._dx_mirror_shared_product_taxes(
                    field_name, current
                )

    def _dx_unlink_non_operational_product_taxes(self):
        operational = operational_companies(self.env)
        templates = self or self.search([])
        for rec in templates:
            for field_name in _TAX_M2M:
                current = rec.sudo()[field_name]
                keep = current.filtered(
                    lambda tax: not tax.company_id or tax.company_id in operational
                )
                if rec.company_id:
                    keep = keep.filtered(lambda tax: tax.company_id == rec.company_id)
                if keep != current:
                    rec.sudo()[field_name] = keep
        return True


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _dx_taxes_for_company(self, company, field_name="taxes_id"):
        self.ensure_one()
        template = self.product_tmpl_id
        if hasattr(template, "_dx_taxes_for_company"):
            return template._dx_taxes_for_company(company, field_name=field_name)
        taxes = self.sudo()[field_name]
        return taxes._filter_taxes_by_company(company or self.env.company)
