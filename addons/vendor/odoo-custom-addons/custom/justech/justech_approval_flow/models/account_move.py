# -*- coding: utf-8 -*-

import hashlib

from odoo import fields, models, _
from odoo.exceptions import UserError

from .snapshot_utils import tax_key

CUSTOMER_TYPES = ("out_invoice", "out_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    justech_approval_state = fields.Selection(
        [
            ("none", "No solicitada"),
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
            ("invalidated", "Invalidada"),
        ],
        string="Estado de aprobación Justech",
        default="none",
        copy=False,
        index=True,
        tracking=True,
    )
    justech_approval_invoice_enabled = fields.Boolean(
        related="company_id.justech_approval_invoice_enabled",
    )
    justech_approval_request_id = fields.Many2one(
        "justech.approval.request",
        compute="_compute_justech_approval_request_id",
    )
    justech_invoice_requires_approval = fields.Boolean(
        compute="_compute_justech_invoice_requires_approval",
    )

    def _compute_justech_approval_request_id(self):
        Request = self.env["justech.approval.request"]
        for move in self:
            pending = Request.search(
                [
                    ("document_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                    ("state", "=", "pending"),
                ],
                order="id desc",
                limit=1,
            )
            move.justech_approval_request_id = pending or Request.search(
                [
                    ("document_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                ],
                order="id desc",
                limit=1,
            )

    def _compute_justech_invoice_requires_approval(self):
        customer = self.filtered(lambda m: m.move_type in CUSTOMER_TYPES)
        (self - customer).justech_invoice_requires_approval = False
        if customer:
            if "sale_line_ids" in self.env["account.move.line"]._fields:
                customer.mapped("invoice_line_ids.sale_line_ids.order_id")
            customer.mapped("reversed_entry_id")
        for move in customer:
            move.justech_invoice_requires_approval = move._justech_invoice_requires_approval()

    def _justech_source_sale_orders(self):
        self.ensure_one()
        if "sale_line_ids" not in self.invoice_line_ids._fields:
            return self.env["sale.order"]
        return self.invoice_line_ids.sale_line_ids.mapped("order_id")

    def _justech_sales_cover_approval(self, orders):
        if not orders:
            return False
        return all(
            order.justech_approval_state == "approved"
            or order.justech_approval_bypass
            or order._justech_approval_bypass()
            for order in orders
        )

    def _justech_invoice_requires_approval(self):
        """Direct customer invoices need approval. Invoices from fully approved/bypassed
        sales do not. Direct credit notes need approval unless they reverse a covered invoice.
        """
        self.ensure_one()
        if not self._justech_approval_in_scope():
            return False
        if self.move_type == "out_refund":
            origin = self.reversed_entry_id
            if origin and origin.exists():
                if origin.justech_approval_state == "approved":
                    return False
                if origin._justech_sales_cover_approval(origin._justech_source_sale_orders()):
                    return False
            if self._justech_sales_cover_approval(self._justech_source_sale_orders()):
                return False
            return True
        if self._justech_sales_cover_approval(self._justech_source_sale_orders()):
            return False
        return True

    def _justech_approval_in_scope(self):
        self.ensure_one()
        if not self.company_id.justech_approval_invoice_enabled:
            return False
        if self.move_type not in CUSTOMER_TYPES:
            return False
        if self.env.context.get("justech_approval_skip"):
            return False
        if "justech_fee_id" in self._fields and self.justech_fee_id:
            return False
        return True

    def _justech_approval_fingerprint(self):
        self.ensure_one()
        lines = tuple(
            sorted(
                (
                    line.product_id.id,
                    round(line.quantity or 0.0, 4),
                    round(line.price_unit or 0.0, 4),
                    round(line.discount or 0.0, 4),
                    tax_key(line.tax_ids),
                )
                for line in self.invoice_line_ids.filtered(
                    lambda l: l.display_type in (False, "product")
                )
            )
        )
        payload = (
            self.partner_id.id,
            self.currency_id.id,
            round(self.amount_untaxed or 0.0, 2),
            round(self.amount_tax or 0.0, 2),
            round(self.amount_total or 0.0, 2),
            lines,
        )
        return hashlib.sha256(repr(payload).encode()).hexdigest()

    def _justech_approval_snapshot_html(self):
        self.ensure_one()
        lines = [
            (
                line.product_id.display_name or line.name or "",
                line.quantity or 0.0,
                line.price_unit or 0.0,
                line.price_subtotal or 0.0,
            )
            for line in self.invoice_line_ids.filtered(
                lambda l: l.display_type in (False, "product")
            )
        ]
        extra = [
            "<strong>Subtotal:</strong> %.2f" % (self.amount_untaxed or 0.0),
            "<strong>Impuestos:</strong> %.2f" % (self.amount_tax or 0.0),
            "<strong>Total:</strong> %.2f" % (self.amount_total or 0.0),
        ]
        return self.env["justech.approval.request"].snapshot_html_from_lines(lines, extra)

    def _justech_maybe_invalidate_approval(self, vals=None):
        if self.env.context.get("justech_approval_skip_fingerprint"):
            return
        Request = self.env["justech.approval.request"]
        for move in self:
            if not move._justech_approval_in_scope() or move.state != "draft":
                continue
            recs = Request.search(
                [
                    ("document_model", "=", "account.move"),
                    ("res_id", "=", move.id),
                    ("state", "in", ("pending", "approved")),
                ]
            )
            if not recs:
                continue
            current = move._justech_approval_fingerprint()
            stale = recs.filtered(lambda r: r.fingerprint and r.fingerprint != current)
            if stale:
                stale.action_invalidate()

    def write(self, vals):
        res = super().write(vals)
        if {"partner_id", "currency_id", "invoice_line_ids", "amount_total"} & set(vals):
            self._justech_maybe_invalidate_approval(vals)
        return res

    def action_post(self):
        need_gate = self.filtered(
            lambda m: m._justech_invoice_requires_approval()
            and m.justech_approval_state != "approved"
            and not self.env.context.get("justech_approval_wizard_submit")
        )
        from odoo.tools import config as odoo_config

        open_wizard = need_gate and (
            self.env.context.get("justech_approval_force_wizard")
            or not odoo_config.get("test_enable")
        )
        if open_wizard:
            if len(self) == 1:
                return need_gate.action_justech_open_request_wizard()
            raise UserError(
                _("Esta factura requiere aprobación antes de confirmarse.")
            )
        return super().action_post()

    def action_justech_request_approval(self, note=None, attachment_ids=None):
        self.ensure_one()
        if not self._justech_approval_in_scope():
            raise UserError(
                _("La aprobación de facturas de cliente no aplica a este documento.")
            )
        if not self._justech_invoice_requires_approval():
            raise UserError(
                _(
                    "Esta factura no requiere aprobación porque proviene de una venta "
                    "ya aprobada o confirmada por un administrador."
                )
            )
        if self.state != "draft":
            raise UserError(_("Solo puede solicitar aprobación sobre una factura en borrador."))
        self.env["justech.approval.request"]._create_for_document(
            self.with_context(justech_approval_wizard_submit=True),
            "out_invoice",
            note=note,
            attachment_ids=attachment_ids,
        )
        return True

    def action_justech_open_request_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Aprobación requerida"),
            "res_model": "justech.approval.sale.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def action_justech_approve(self):
        self.ensure_one()
        request = self.justech_approval_request_id.filtered(lambda r: r.state == "pending")
        if not request:
            raise UserError(_("No hay una solicitud pendiente."))
        return request.action_open_approve_wizard()

    def action_justech_reject_wizard(self):
        self.ensure_one()
        request = self.justech_approval_request_id.filtered(lambda r: r.state == "pending")
        if not request:
            raise UserError(_("No hay una solicitud pendiente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar aprobación"),
            "res_model": "justech.approval.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": request.id},
        }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def write(self, vals):
        res = super().write(vals)
        material = {"product_id", "quantity", "price_unit", "discount", "tax_ids"}
        if material & set(vals):
            self.mapped("move_id").filtered(
                lambda m: m.state == "draft" and m.move_type in CUSTOMER_TYPES
            )._justech_maybe_invalidate_approval(vals)
        return res
