# -*- coding: utf-8 -*-

import hashlib

from odoo import fields, models, _
from odoo.exceptions import UserError

from .snapshot_utils import tax_key


class SaleOrder(models.Model):
    _inherit = ["sale.order", "justech.approval.policy.mixin"]

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
    justech_approval_sale_enabled = fields.Boolean(
        related="company_id.justech_approval_sale_enabled",
    )
    justech_approval_request_id = fields.Many2one(
        "justech.approval.request",
        compute="_compute_justech_approval_request_id",
    )
    justech_approval_can_bypass = fields.Boolean(
        compute="_compute_justech_approval_can_bypass",
    )
    justech_approval_bypass = fields.Boolean(copy=False, readonly=True)
    justech_approval_bypass_user_id = fields.Many2one(
        "res.users", copy=False, readonly=True
    )
    justech_approval_bypass_date = fields.Datetime(copy=False, readonly=True)

    def _compute_justech_approval_request_id(self):
        Request = self.env["justech.approval.request"]
        for order in self:
            pending = Request.search(
                [
                    ("document_model", "=", "sale.order"),
                    ("res_id", "=", order.id),
                    ("state", "=", "pending"),
                ],
                order="id desc",
                limit=1,
            )
            order.justech_approval_request_id = pending or Request.search(
                [
                    ("document_model", "=", "sale.order"),
                    ("res_id", "=", order.id),
                ],
                order="id desc",
                limit=1,
            )

    def _compute_justech_approval_can_bypass(self):
        can = self._justech_user_can_bypass_approval()
        for order in self:
            order.justech_approval_can_bypass = can

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == "form":
            for button in arch.xpath("//button[@name='action_add_purchase_orders']"):
                button.set("invisible", "True")
        return arch, view

    def _justech_approval_bypass(self):
        self.ensure_one()
        if self.env.context.get("justech_approval_skip"):
            return True
        if "justech_fee_id" in self._fields and self.justech_fee_id:
            return True
        return False

    def _justech_sale_approval_required(self):
        self.ensure_one()
        if self._justech_approval_bypass():
            return False
        if not self.company_id.justech_approval_sale_enabled:
            return False
        if self._justech_user_can_bypass_approval():
            return False
        return True

    def _justech_mark_approval_bypass(self):
        for order in self:
            if not order.company_id.justech_approval_sale_enabled:
                continue
            if order.justech_approval_bypass and order.justech_approval_state == "approved":
                continue
            reason = order._justech_bypass_reason()
            order.with_context(justech_approval_skip_fingerprint=True).sudo().write(
                {
                    "justech_approval_bypass": True,
                    "justech_approval_bypass_user_id": self.env.user.id,
                    "justech_approval_bypass_date": fields.Datetime.now(),
                    "justech_approval_state": "approved",
                }
            )
            if reason == "admin":
                body = _("Documento confirmado directamente por un administrador.")
            else:
                body = _("Documento confirmado mediante autoaprobación.")
            order.sudo().message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _justech_check_sale_approval(self):
        for order in self:
            if not order._justech_sale_approval_required():
                continue
            if order.justech_approval_state != "approved":
                raise UserError(
                    _("Esta cotización requiere aprobación antes de poder confirmarse.")
                )

    def _justech_approval_fingerprint(self):
        self.ensure_one()
        lines = tuple(
            sorted(
                (
                    line.product_id.id,
                    round(line.product_uom_qty or 0.0, 4),
                    round(line.price_unit or 0.0, 4),
                    round(line.discount or 0.0, 4),
                    tax_key(line.tax_ids if "tax_ids" in line._fields else line.tax_id),
                )
                for line in self.order_line.filtered(lambda l: not l.display_type)
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
                line.product_uom_qty or 0.0,
                line.price_unit or 0.0,
                line.price_subtotal or 0.0,
            )
            for line in self.order_line.filtered(lambda l: not l.display_type)
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
        for order in self:
            if not order.company_id.justech_approval_sale_enabled:
                continue
            recs = Request.search(
                [
                    ("document_model", "=", "sale.order"),
                    ("res_id", "=", order.id),
                    ("state", "in", ("pending", "approved")),
                ]
            )
            if not recs:
                continue
            current = order._justech_approval_fingerprint()
            stale = recs.filtered(lambda r: r.fingerprint and r.fingerprint != current)
            if stale and order.state in ("draft", "sent"):
                stale.action_invalidate()

    def write(self, vals):
        res = super().write(vals)
        if {"partner_id", "currency_id", "order_line", "amount_total"} & set(vals):
            self._justech_maybe_invalidate_approval(vals)
        return res

    def _confirmation_error_message(self):
        msg = super()._confirmation_error_message()
        if msg:
            return msg
        if self._justech_sale_approval_required() and self.justech_approval_state != "approved":
            return _("Esta cotización requiere aprobación antes de poder confirmarse.")
        return False

    def action_confirm(self):
        need_gate = self.filtered(
            lambda o: o._justech_sale_approval_required()
            and o.justech_approval_state != "approved"
        )
        from odoo.tools import config as odoo_config

        open_wizard = need_gate and (
            self.env.context.get("justech_approval_force_wizard")
            or not odoo_config.get("test_enable")
        )
        if open_wizard:
            if len(self) == 1:
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Aprobación requerida"),
                    "res_model": "justech.approval.sale.confirm.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {"default_sale_order_id": self.id},
                }
            raise UserError(
                _("Esta cotización requiere aprobación antes de confirmarse.")
            )
        return super().action_confirm()

    def _action_confirm(self):
        self._justech_check_sale_approval()
        res = super()._action_confirm()
        to_mark = self.filtered(
            lambda o: o.company_id.justech_approval_sale_enabled
            and o._justech_user_can_bypass_approval()
            and o.state in ("sale", "done")
        )
        if to_mark:
            to_mark._justech_mark_approval_bypass()
        return res

    def action_justech_request_approval(self, note=None, attachment_ids=None):
        self.ensure_one()
        if not self.company_id.justech_approval_sale_enabled:
            raise UserError(_("La aprobación de cotizaciones no está activa en esta empresa."))
        if self.state not in ("draft", "sent"):
            raise UserError(_("Solo puede solicitar aprobación sobre una cotización en borrador."))
        self.env["justech.approval.request"]._create_for_document(
            self.with_context(justech_approval_wizard_submit=True),
            "sale_order",
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
            "context": {"default_sale_order_id": self.id},
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


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def write(self, vals):
        res = super().write(vals)
        material = {"product_id", "product_uom_qty", "price_unit", "discount", "tax_id", "tax_ids"}
        if material & set(vals):
            self.mapped("order_id")._justech_maybe_invalidate_approval(vals)
        return res
