"""Confía las cuentas bancarias de las compañías Doralex.

Odoo 19 bloquea Confirmar/Publicar en facturas inbound si
res.partner.bank.allow_out_payment es falso. Quien solo factura no puede
marcar la cuenta como de confianza (RedirectWarning queda en UserError).
Solo se marcan cuentas cuyo titular es un res.company.
No se otorgan grupos, no se tocan cuentas de proveedores/clientes, no se
consume NCF.
"""

from odoo import api, models

_TRUST_CTX = "dx_trust_company_bank"


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    def _dx_is_company_owned_bank(self):
        self.ensure_one()
        return bool(self.partner_id) and self.partner_id._dx_is_company_partner()

    def _dx_trust_if_company_owned(self):
        to_trust = self.sudo().filtered(
            lambda bank: not bank.allow_out_payment and bank._dx_is_company_owned_bank()
        )
        if to_trust:
            to_trust.with_context(install_mode=True, **{_TRUST_CTX: True}).write(
                {"allow_out_payment": True}
            )
        return to_trust

    @api.model
    def _dx_trust_company_owned_banks(self):
        partner_ids = self.env["res.company"].sudo().search([]).mapped("partner_id").ids
        if not partner_ids:
            return self.browse()
        banks = self.sudo().search([("partner_id", "in", partner_ids)])
        return banks._dx_trust_if_company_owned()

    @api.model_create_multi
    def create(self, vals_list):
        banks = super().create(vals_list)
        banks._dx_trust_if_company_owned()
        return banks
