# -*- coding: utf-8 -*-
"""Redirige el botón nativo de factura al wizard único Justech."""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    justech_withholding_line_ids = fields.One2many(
        "justech.payment.withholding.line",
        "move_id",
        string="Retenciones aplicadas",
        copy=False,
    )
    justech_withholding_count = fields.Integer(
        compute="_compute_justech_withholding_count",
        string="Retenciones",
    )

    @api.depends("justech_withholding_line_ids")
    def _compute_justech_withholding_count(self):
        for move in self:
            move.justech_withholding_count = len(move.justech_withholding_line_ids)

    def action_justech_view_withholdings(self):
        self.ensure_one()
        lines = self.justech_withholding_line_ids
        if not lines:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Retenciones",
            "res_model": "justech.payment.withholding.line",
            "view_mode": "list,form",
            "domain": [("id", "in", lines.ids)],
        }

    def action_register_payment(self):
        """Único camino operativo: justech.payment.partner.wizard.

        Soporta una o varias facturas del mismo commercial_partner.
        El wizard nativo account.payment.register se usa internamente al confirmar.
        """
        moves = self.filtered(
            lambda m: m.state == "posted"
            and m.payment_state not in ("paid", "reversed", "invoicing_legacy")
            and not m.currency_id.is_zero(m.amount_residual)
            and m.is_invoice(include_receipts=True)
        )
        if not moves:
            return super().action_register_payment()

        commercial = moves.mapped("commercial_partner_id")
        if len(commercial) > 1:
            from odoo.exceptions import UserError

            raise UserError(
                "Seleccione facturas del mismo cliente o proveedor comercial "
                "para registrar un solo cobro/pago."
            )
        sale_docs = moves.filtered(lambda m: m.is_sale_document(include_receipts=True))
        purchase_docs = moves.filtered(lambda m: m.is_purchase_document(include_receipts=True))
        if sale_docs and purchase_docs:
            from odoo.exceptions import UserError

            raise UserError(
                "No se pueden mezclar facturas de cliente y de proveedor en el mismo pago."
            )

        partner_type = "customer" if sale_docs else "supplier"
        action_xmlid = (
            "justech_l10n_do_payments_withholding.action_justech_register_customer_payment"
            if partner_type == "customer"
            else "justech_l10n_do_payments_withholding.action_justech_register_vendor_payment"
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(action_xmlid)
        ctx = dict(self.env.context)
        ctx.update(
            {
                "default_partner_type": partner_type,
                "default_partner_id": moves[0].partner_id.id,
                "default_currency_id": moves[0].currency_id.id,
                "active_model": "account.move",
                "active_ids": moves.ids,
                "active_id": moves[0].id,
                "justech_preselect_move_ids": moves.ids,
            }
        )
        action["context"] = ctx
        return action
