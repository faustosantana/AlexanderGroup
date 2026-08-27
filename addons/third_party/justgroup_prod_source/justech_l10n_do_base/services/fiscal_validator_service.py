"""Servicio Odoo — delegación a validadores puros."""
from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.justech_l10n_do_base.validators import fiscal_context, ncf_format, rnc_format


class JustechDoFiscalValidatorService(models.AbstractModel):
    _name = "justech.do.fiscal.validator.service"
    _description = "Justech Fiscal Validator Service"

    def normalize_vat(self, vat):
        return rnc_format.normalize_vat(vat)

    def is_valid_rnc_format(self, vat):
        return rnc_format.is_valid_rnc_format(vat)

    def validate_rnc_format(self, vat, *, error_message=None):
        if not rnc_format.is_valid_rnc_format(vat):
            raise ValidationError(
                error_message
                or _("Dominican RNC must be 9 to 11 digits (spaces/dashes allowed).")
            )
        return rnc_format.normalize_vat(vat)

    def normalize_ncf(self, ncf):
        return ncf_format.normalize_ncf(ncf)

    def validate_ncf_format(self, ncf):
        try:
            return ncf_format.validate_ncf_format(ncf)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def parse_ncf(self, ncf):
        return ncf_format.parse_ncf(ncf)

    def fiscal_module_for_move_type(self, move_type):
        return fiscal_context.fiscal_module_for_move_type(move_type)

    def fiscal_duplicate_key_v2(self, company, move, ncf):
        return fiscal_context.fiscal_duplicate_key_v2(
            company_id=company.id,
            move_type=move.move_type,
            ncf=ncf,
            company_vat=company.vat or "",
            partner_vat=move.partner_id.vat if move.partner_id else "",
        )
