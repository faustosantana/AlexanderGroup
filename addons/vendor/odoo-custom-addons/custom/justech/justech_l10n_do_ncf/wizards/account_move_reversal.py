# -*- coding: utf-8 -*-
"""Extiende el wizard estándar Odoo 19 account.move.reversal (sin motor paralelo)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    justech_needs_vendor_cn_data = fields.Boolean(compute="_compute_justech_vendor_cn")
    justech_vendor_cn_ncf = fields.Char(
        string="NCF de la nota de crédito del proveedor",
        help="Obligatorio para compras en modo «Documento recibido».",
    )
    justech_vendor_cn_date = fields.Date(
        string="Fecha del comprobante del proveedor",
        help="Fecha del NCF de la nota de crédito recibida.",
    )
    justech_replace_mode = fields.Boolean(
        string="Modo reemplazo",
        compute="_compute_justech_replace_mode",
    )

    @api.depends_context("justech_reverse_and_replace")
    def _compute_justech_replace_mode(self):
        flag = bool(self.env.context.get("justech_reverse_and_replace"))
        for wiz in self:
            wiz.justech_replace_mode = flag

    @api.depends(
        "move_ids",
        "move_ids.move_type",
        "move_ids.justech_do_purchase_registration_mode",
    )
    def _compute_justech_vendor_cn(self):
        for wiz in self:
            needs = False
            for move in wiz.move_ids:
                mode = getattr(move, "justech_do_purchase_registration_mode", False) or "received"
                if move.move_type == "in_invoice" and mode == "received":
                    needs = True
                    break
            wiz.justech_needs_vendor_cn_data = needs

    def _justech_validate_vendor_cn_data(self):
        self.ensure_one()
        if not self.justech_needs_vendor_cn_data:
            return
        if not (self.justech_vendor_cn_ncf or "").strip():
            raise UserError(
                _(
                    "Para revertir una factura de proveedor recibida debe indicar "
                    "el NCF de la nota de crédito del proveedor."
                )
            )
        if not self.justech_vendor_cn_date:
            raise UserError(
                _(
                    "Para revertir una factura de proveedor recibida debe indicar "
                    "la fecha del comprobante del proveedor."
                )
            )

    def _justech_credit_doc_type(self):
        Doc = self.env["l10n_latam.document.type"].sudo()
        credit = Doc.search(
            [("doc_code_prefix", "=", "B04"), ("internal_type", "=", "credit_note")],
            limit=1,
        )
        return credit or Doc.search([("doc_code_prefix", "=", "B04")], limit=1)

    def _justech_apply_vendor_cn_on_refunds(self, new_moves):
        """Completa datos fiscales DO en NC de compra recibida (localización)."""
        self.ensure_one()
        if not self.justech_needs_vendor_cn_data:
            return
        ncf = (self.justech_vendor_cn_ncf or "").strip().upper()
        credit_type = self._justech_credit_doc_type()
        for rev in new_moves.filtered(lambda m: m.move_type == "in_refund"):
            vals = {
                "justech_do_purchase_registration_mode": "received",
                "invoice_date": self.justech_vendor_cn_date or self.date or rev.invoice_date,
            }
            if "l10n_latam_document_number" in rev._fields:
                vals["l10n_latam_document_number"] = ncf
            if credit_type and "l10n_latam_document_type_id" in rev._fields:
                vals["l10n_latam_document_type_id"] = credit_type.id
            origin = rev.reversed_entry_id
            if (
                origin
                and "justech_do_expense_type_id" in rev._fields
                and origin.justech_do_expense_type_id
            ):
                vals["justech_do_expense_type_id"] = origin.justech_do_expense_type_id.id
            rev.with_context(skip_invoice_sync=True).write(vals)

    def _justech_link_replacements(self, origin_moves, new_moves):
        drafts = new_moves.filtered(
            lambda m: m.move_type in ("out_invoice", "in_invoice") and m.state == "draft"
        )
        if not drafts:
            return
        for origin, draft in zip(origin_moves, drafts):
            if "justech_do_replacement_move_id" in origin._fields:
                origin.justech_do_replacement_move_id = draft.id
            origin.message_post(
                body=_(
                    "Reversión con reemplazo: factura sustituta creada en borrador %(draft)s."
                )
                % {"draft": draft.display_name}
            )

    def reverse_moves(self, is_modify=False):
        self._justech_validate_vendor_cn_data()
        origins = self.move_ids
        action = super().reverse_moves(is_modify=is_modify)
        if self.new_move_ids:
            refunds = self.new_move_ids.filtered(
                lambda m: m.move_type in ("out_refund", "in_refund")
            )
            self._justech_apply_vendor_cn_on_refunds(refunds)
            if is_modify:
                self._justech_link_replacements(origins, self.new_move_ids)
        return action

    def refund_moves(self):
        # Abierto desde «Revertir y reemplazar» → modify_moves del estándar Odoo 19.
        if self.env.context.get("justech_reverse_and_replace") or self.justech_replace_mode:
            return self.modify_moves()
        return super().refund_moves()
