"""Reglas de negocio fiscal pre-post — B14, RD$250k, exportaciones."""
from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.justech_l10n_do_ncf.validators import business_rules


class JustechDoNcfBusinessRulesService(models.AbstractModel):
    _name = "justech.do.ncf.business.rules.service"
    _description = "NCF Business Rules Service"

    def validate_before_post(self, move):
        move.ensure_one()
        if not self.env["justech.do.fiscal.config.service"].is_fiscal_enabled(move.company_id):
            return
        doc = move.justech_do_document_type_id or move._justech_resolve_document_type()
        partner = move.partner_id.commercial_partner_id if move.partner_id else False
        if move.move_type in ("out_invoice", "out_refund") and partner:
            state = partner.justech_do_fiscal_config_state
            has_persisted_default = bool(partner.justech_do_default_document_type_id)
            # Cliente nuevo: exige validación/configuración persistida (no basta sugerencia).
            if state == "pending_new" and not has_persisted_default:
                raise UserError(
                    _(
                        "Cliente %(partner)s pendiente de validar. "
                        "Valide el RNC/Cédula y asigne el comprobante fiscal "
                        "antes de publicar la factura.",
                        partner=partner.display_name,
                    )
                )
            if state == "needs_review" and not (doc and has_persisted_default):
                raise UserError(
                    _(
                        "Cliente %(partner)s requiere revisión fiscal "
                        "(%(source)s). No se puede publicar hasta resolver el comprobante.",
                        partner=partner.display_name,
                        source=partner.justech_do_fiscal_config_source or state,
                    )
                )
            if not doc and state not in ("confirmed_history", "validated_padron", "not_applicable"):
                raise UserError(
                    _(
                        "Cliente %(partner)s sin comprobante fiscal resoluble. "
                        "Confirme histórico o valide con padrón antes de publicar.",
                        partner=partner.display_name,
                    )
                )
        if not doc:
            return
        prefix = doc.prefix
        partner_has_rnc = bool(move.partner_id and move.partner_id.justech_do_has_rnc())
        line_taxes = []
        for line in move.invoice_line_ids:
            for tax in line.tax_ids:
                line_taxes.append(
                    {"amount": tax.amount, "type_tax_use": tax.type_tax_use}
                )
        line_products = [
            {
                "type": line.product_id.type if line.product_id else "service",
                "is_storable": getattr(line.product_id, "is_storable", False),
            }
            for line in move.invoice_line_ids
        ]
        partner_country = move.partner_id.country_id.code if move.partner_id.country_id else None

        checks = [
            business_rules.validate_b14_no_itbis(prefix=prefix, line_taxes=line_taxes),
            business_rules.validate_high_amount_requires_rnc(
                prefix=prefix,
                move_type=move.move_type,
                amount_total=move.amount_total,
                partner_has_rnc=partner_has_rnc,
            ),
            business_rules.validate_export_invoice(
                prefix=prefix,
                move_type=move.move_type,
                partner_country_code=partner_country,
                line_products=line_products,
            ),
        ]
        for msg in checks:
            if msg:
                raise UserError(_(msg))
