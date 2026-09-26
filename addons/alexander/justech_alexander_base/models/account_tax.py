from odoo import _, models
from odoo.exceptions import AccessError, UserError

_CROSS_COMPANY_TAX_MSG = (
    "El impuesto seleccionado pertenece a otra empresa. "
    "Revise la configuración fiscal del producto."
)


class AccountTax(models.Model):
    _inherit = "account.tax"

    def _dx_accessible_taxes(self):
        """Taxes the current company switcher may read. Does not widen access."""
        if not self:
            return self
        company_ids = self.env.companies.ids
        if not company_ids:
            return self.browse()
        allowed_ids = set(
            self.sudo().filtered_domain([("company_id", "parent_of", company_ids)]).ids
        )
        return self.browse([tax_id for tax_id in self.ids if tax_id in allowed_ids])

    def _dx_cross_company_tax_msg(self):
        other = (self.sudo() - self._dx_accessible_taxes().sudo())[:1]
        company_name = other.company_id.display_name if other else ""
        if company_name:
            return _(
                "%(msg)s Impuesto de %(company)s.",
                msg=_CROSS_COMPANY_TAX_MSG,
                company=company_name,
            )
        return _(_CROSS_COMPANY_TAX_MSG)

    def _filter_taxes_by_company(self, company_id):
        """Native hierarchy filter without reading foreign-company tax fields."""
        if not self:
            return self
        taxes, company = self.env["account.tax"], company_id
        sudo_taxes = self.sudo()
        while not taxes and company:
            match_ids = sudo_taxes.filtered(lambda tax: tax.company_id == company).ids
            taxes = self.browse(match_ids)
            company = company.sudo().parent_id
        return taxes

    def check_access(self, operation, *args, **kwargs):
        if operation == "read" and self and not self.env.su:
            allowed = self._dx_accessible_taxes()
            if len(allowed) != len(self):
                if not allowed:
                    raise UserError(self._dx_cross_company_tax_msg())
                return allowed.check_access(operation, *args, **kwargs)
        try:
            return super().check_access(operation, *args, **kwargs)
        except AccessError as exc:
            if operation == "read" and self and not self.env.su:
                raise UserError(self._dx_cross_company_tax_msg()) from exc
            raise

    def read(self, fields=None, load="_classic_read"):
        if self and not self.env.su and not self.env.context.get("dx_tax_access_skip"):
            allowed = self._dx_accessible_taxes()
            if len(allowed) != len(self):
                if not allowed:
                    raise UserError(self._dx_cross_company_tax_msg())
                return allowed.with_context(dx_tax_access_skip=True).read(
                    fields=fields, load=load
                )
        return super().read(fields=fields, load=load)

    def web_read(self, specification):
        if self and not self.env.su and not self.env.context.get("dx_tax_access_skip"):
            allowed = self._dx_accessible_taxes()
            if len(allowed) != len(self):
                if not allowed:
                    raise UserError(self._dx_cross_company_tax_msg())
                return allowed.with_context(dx_tax_access_skip=True).web_read(
                    specification
                )
        return super().web_read(specification)
