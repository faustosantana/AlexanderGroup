from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.fields import Command

from .account_tax import _CROSS_COMPANY_TAX_MSG
from .catalog import operational_companies

_TAX_M2M = ("taxes_id", "supplier_taxes_id")
_GUARD_CTX = "dx_skip_tax_company_guard"


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

    @api.model
    def default_get(self, fields_list):
        """Only the current company's ITBIS. Sibling taxes are mirrored on save."""
        defaults = super().default_get(fields_list)
        if "taxes_id" in fields_list:
            defaults["taxes_id"] = [
                Command.set(self.env.company.account_sale_tax_id.ids)
            ]
        if "supplier_taxes_id" in fields_list:
            defaults["supplier_taxes_id"] = [
                Command.set(self.env.company.account_purchase_tax_id.ids)
            ]
        return defaults

    def _dx_taxes_for_company(self, company, field_name="taxes_id"):
        """Native per-company taxes for a shared product. Never duplicates products."""
        self.ensure_one()
        company = company or self.env.company
        taxes = self.sudo()[field_name]
        return taxes._filter_taxes_by_company(company)

    def _dx_visible_product_taxes(self, field_name):
        """Taxes the switcher may show. Sibling companies stay stored, not displayed."""
        self.ensure_one()
        allowed = self.env.companies
        visible = self.sudo()[field_name].filtered(
            lambda tax: not tax.company_id or tax.company_id in allowed
        )
        return self.env["account.tax"].browse(visible.ids)

    def _dx_mask_tax_rows(self, rows):
        if self.env.su or self.env.context.get(_GUARD_CTX):
            return rows
        if self.env.context.get("dx_tax_access_skip"):
            return rows
        by_id = {rec.id: rec for rec in self}
        for row in rows:
            rec = by_id.get(row.get("id"))
            if not rec:
                continue
            for fname in _TAX_M2M:
                if fname not in row:
                    continue
                row[fname] = rec._dx_visible_product_taxes(fname).ids
        return rows

    def read(self, fields=None, load="_classic_read"):
        rows = super().read(fields=fields, load=load)
        if fields is not None and not any(name in fields for name in _TAX_M2M):
            return rows
        return self._dx_mask_tax_rows(rows)

    def web_read(self, specification):
        rows = super().web_read(specification)
        if self.env.su or self.env.context.get(_GUARD_CTX):
            return rows
        if not any(name in specification for name in _TAX_M2M):
            return rows
        by_id = {rec.id: rec for rec in self}
        for row in rows:
            rec = by_id.get(row.get("id"))
            if not rec:
                continue
            for fname in _TAX_M2M:
                if fname not in specification or fname not in row:
                    continue
                visible = rec._dx_visible_product_taxes(fname)
                spec = specification.get(fname) or {}
                child = spec.get("fields")
                if child:
                    row[fname] = visible.with_context(dx_tax_access_skip=True).web_read(
                        child
                    )
                else:
                    row[fname] = visible.ids
        return rows

    def search_read(
        self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs
    ):
        rows = super().search_read(
            domain=domain,
            fields=fields,
            offset=offset,
            limit=limit,
            order=order,
            **kwargs,
        )
        if fields is not None and not any(name in fields for name in _TAX_M2M):
            return rows
        records = self.browse([row["id"] for row in rows if row.get("id")])
        return records._dx_mask_tax_rows(rows)

    def _construct_tax_string(self, price):
        return super(
            ProductTemplate, self.sudo().with_company(self.env.company)
        )._construct_tax_string(price)

    def _dx_equivalent_tax(self, tax, target_company):
        if not tax or not target_company:
            return self.env["account.tax"]
        if tax.company_id == target_company:
            return tax
        default = self.env["account.tax"]
        if tax.type_tax_use == "sale":
            default = target_company.sudo().account_sale_tax_id
        elif tax.type_tax_use == "purchase":
            default = target_company.sudo().account_purchase_tax_id
        if (
            default
            and default.amount_type == tax.amount_type
            and default.amount == tax.amount
        ):
            return default
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

    def _dx_set_product_taxes(self, field_name, taxes):
        """Write taxes without re-entering the company guard (mirror uses sudo)."""
        self.sudo().with_context(**{_GUARD_CTX: True}).write(
            {field_name: [Command.set(taxes.ids)]}
        )

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
        operational = operational_companies(self.env)
        mapped = self.env["account.tax"]
        unmapped = self.env["account.tax"]
        for tax in incoming_bad:
            # Native account._force_default_tax links every other company's
            # default, including the technical template (15%). Drop those.
            if tax.company_id and tax.company_id not in operational:
                continue
            equivalent = self._dx_equivalent_tax(tax, self.env.company)
            if equivalent and equivalent.company_id in allowed:
                mapped |= equivalent
            else:
                unmapped |= tax
        if unmapped:
            raise ValidationError(_CROSS_COMPANY_TAX_MSG)
        incoming_ok |= mapped
        for rec in self:
            existing = rec.sudo()[field_name]
            keep = existing.filtered(lambda tax: tax.company_id not in allowed)
            merged = keep | incoming_ok
            if not rec.company_id:
                merged = rec._dx_mirror_shared_product_taxes(field_name, merged)
            elif rec.company_id:
                merged = merged.filtered(lambda tax: tax.company_id == rec.company_id)
            if merged != existing:
                rec._dx_set_product_taxes(field_name, merged)

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
        if self.env.context.get(_GUARD_CTX):
            return super().write(vals)
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
                        rec._dx_set_product_taxes(field_name, defaults)
                    continue
                rec._dx_set_product_taxes(
                    field_name,
                    rec._dx_mirror_shared_product_taxes(field_name, current),
                )

    def _dx_unlink_non_operational_product_taxes(self):
        """Drop template-company and foreign taxes from the native M2M tables."""
        operational = tuple(operational_companies(self.env).ids) or (0,)
        cr = self.env.cr
        if self:
            cr.execute(
                """
                DELETE FROM product_taxes_rel rel
                USING product_template pt, account_tax tax
                WHERE rel.prod_id = pt.id AND rel.tax_id = tax.id
                  AND pt.id IN %s
                  AND (
                    (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
                    OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                        AND tax.company_id <> pt.company_id)
                  )
                """,
                (tuple(self.ids), operational),
            )
            cr.execute(
                """
                DELETE FROM product_supplier_taxes_rel rel
                USING product_template pt, account_tax tax
                WHERE rel.prod_id = pt.id AND rel.tax_id = tax.id
                  AND pt.id IN %s
                  AND (
                    (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
                    OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                        AND tax.company_id <> pt.company_id)
                  )
                """,
                (tuple(self.ids), operational),
            )
        else:
            cr.execute(
                """
                DELETE FROM product_taxes_rel rel
                USING product_template pt, account_tax tax
                WHERE rel.prod_id = pt.id AND rel.tax_id = tax.id
                  AND (
                    (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
                    OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                        AND tax.company_id <> pt.company_id)
                  )
                """,
                (operational,),
            )
            cr.execute(
                """
                DELETE FROM product_supplier_taxes_rel rel
                USING product_template pt, account_tax tax
                WHERE rel.prod_id = pt.id AND rel.tax_id = tax.id
                  AND (
                    (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
                    OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                        AND tax.company_id <> pt.company_id)
                  )
                """,
                (operational,),
            )
        self.invalidate_recordset(["taxes_id", "supplier_taxes_id"])
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

    def _dx_visible_product_taxes(self, field_name):
        self.ensure_one()
        return self.product_tmpl_id._dx_visible_product_taxes(field_name)

    def _dx_mask_tax_rows(self, rows):
        if self.env.su or self.env.context.get(_GUARD_CTX):
            return rows
        if self.env.context.get("dx_tax_access_skip"):
            return rows
        by_id = {rec.id: rec for rec in self}
        for row in rows:
            rec = by_id.get(row.get("id"))
            if not rec:
                continue
            for fname in _TAX_M2M:
                if fname not in row:
                    continue
                row[fname] = rec._dx_visible_product_taxes(fname).ids
        return rows

    def read(self, fields=None, load="_classic_read"):
        rows = super().read(fields=fields, load=load)
        if fields is not None and not any(name in fields for name in _TAX_M2M):
            return rows
        return self._dx_mask_tax_rows(rows)

    def web_read(self, specification):
        rows = super().web_read(specification)
        if self.env.su or self.env.context.get(_GUARD_CTX):
            return rows
        if not any(name in specification for name in _TAX_M2M):
            return rows
        by_id = {rec.id: rec for rec in self}
        for row in rows:
            rec = by_id.get(row.get("id"))
            if not rec:
                continue
            for fname in _TAX_M2M:
                if fname not in specification or fname not in row:
                    continue
                visible = rec._dx_visible_product_taxes(fname)
                spec = specification.get(fname) or {}
                child = spec.get("fields")
                if child:
                    row[fname] = visible.with_context(dx_tax_access_skip=True).web_read(
                        child
                    )
                else:
                    row[fname] = visible.ids
        return rows

    def _dx_visible_product_taxes(self, field_name):
        self.ensure_one()
        return self.product_tmpl_id._dx_visible_product_taxes(field_name)

    def read(self, fields=None, load="_classic_read"):
        rows = super().read(fields=fields, load=load)
        if fields is not None and not any(name in fields for name in _TAX_M2M):
            return rows
        return self._dx_mask_tax_rows(rows)

    def web_read(self, specification):
        return self.env["product.template"].web_read.__get__(self, type(self))(
            specification
        )
