# -*- coding: utf-8 -*-
"""19.0.4.0.0 — Capa UX de negocio sobre operaciones de margen.

Traduce estados internos (draft/detected/confidence/…) a lenguaje de
Compras / Finanzas sin alterar la máquina de estados técnica.
"""
from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero
from markupsafe import Markup, escape

BUSINESS_STATES = [
    ("to_review", "Por revisar"),
    ("need_relation", "Falta relacionar compra con venta"),
    ("need_vendor_bill", "Falta factura del proveedor"),
    ("need_customer_invoice", "Falta factura del cliente"),
    ("suggested", "Relación sugerida por el sistema"),
    ("purchase_validated", "Revisado por Compras"),
    ("finance_pending", "Pendiente de aprobación de Finanzas"),
    ("approved", "Aprobado"),
    ("rejected", "Rechazado"),
    ("closed", "Cerrado"),
]

PENDING_ACTORS = [
    ("purchases", "Compras"),
    ("finance", "Finanzas"),
    ("sales", "Ventas"),
    ("none", "Ninguno"),
]

COMMERCIAL_COST_STATUS = [
    ("pending", "Costos pendientes"),
    ("partial", "Cobertura parcial"),
    ("linked", "Costos relacionados"),
    ("confirmed", "Costos reales confirmados"),
]


class PurchaseSaleMarginTransactionUX(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    company_id = fields.Many2one(string="Empresa")
    customer_id = fields.Many2one(string="Cliente")

    business_state = fields.Selection(
        BUSINESS_STATES,
        string="Situación",
        compute="_compute_ux_guidance",
        store=True,
        index=True,
    )
    business_state_help = fields.Text(
        string="Explicación del estado",
        compute="_compute_ux_guidance",
        store=True,
    )
    pending_reason = fields.Text(
        string="¿Qué falta?",
        compute="_compute_ux_guidance",
        store=True,
    )
    pending_action = fields.Char(
        string="Acción recomendada",
        compute="_compute_ux_guidance",
        store=True,
    )
    pending_actor = fields.Selection(
        PENDING_ACTORS,
        string="Quién debe actuar",
        compute="_compute_ux_guidance",
        store=True,
    )
    pending_action_banner = fields.Char(
        string="Acción pendiente",
        compute="_compute_ux_guidance",
        store=True,
    )
    commercial_cost_status = fields.Selection(
        COMMERCIAL_COST_STATUS,
        string="Estado comercial de costos",
        compute="_compute_commercial_cost_status",
    )
    commercial_cost_status_label = fields.Char(
        string="Estado costos",
        compute="_compute_commercial_cost_status",
    )
    cost_status_compact_html = fields.Html(
        string="Resumen de costos",
        compute="_compute_commercial_cost_status",
        sanitize=False,
    )
    show_legacy_pending_banner = fields.Boolean(
        compute="_compute_commercial_cost_status",
    )

    amount_to_collect = fields.Monetary(
        string="Pendiente de cobro",
        compute="_compute_payment_balances",
        store=True,
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    amount_to_pay = fields.Monetary(
        string="Pendiente de pago",
        compute="_compute_payment_balances",
        store=True,
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view,justech_purchase_sale_margin_control.group_margin_sec_cxp_view",
    )
    amount_collected = fields.Monetary(
        string="Total cobrado",
        compute="_compute_payment_balances",
        store=True,
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    amount_paid_vendor = fields.Monetary(
        string="Total pagado a proveedores",
        compute="_compute_payment_balances",
        store=True,
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view,justech_purchase_sale_margin_control.group_margin_sec_cxp_view",
    )
    invalid_cost_alert = fields.Text(
        string="Alerta de costo",
        compute="_compute_invalid_cost_alert",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    display_sale_amount = fields.Monetary(
        string="Venta total",
        compute="_compute_display_amounts",
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    display_cost_amount = fields.Monetary(
        string="Costo total",
        compute="_compute_display_amounts",
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    display_margin_amount = fields.Monetary(
        string="Margen",
        compute="_compute_display_amounts",
        currency_field="company_currency_id",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    display_margin_pct = fields.Float(
        string="Margen %",
        compute="_compute_display_amounts",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    primary_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        compute="_compute_primary_docs",
        store=True,
    )
    primary_sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        compute="_compute_primary_docs",
        store=True,
    )
    primary_purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Orden de compra",
        compute="_compute_primary_docs",
        store=True,
    )
    primary_customer_invoice_id = fields.Many2one(
        "account.move",
        string="Factura de cliente",
        compute="_compute_primary_docs",
        store=True,
    )
    primary_vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura de proveedor",
        compute="_compute_primary_docs",
        store=True,
    )

    @api.depends(
        "supplier_ids",
        "sale_order_ids",
        "purchase_order_ids",
        "customer_invoice_ids",
        "vendor_bill_ids",
    )
    def _compute_primary_docs(self):
        for rec in self:
            rec.primary_supplier_id = rec.supplier_ids[:1] or False
            if not rec.primary_supplier_id and rec.purchase_order_ids:
                rec.primary_supplier_id = rec.purchase_order_ids[:1].partner_id
            rec.primary_sale_order_id = rec.sale_order_ids[:1]
            rec.primary_purchase_order_id = rec.purchase_order_ids[:1]
            rec.primary_customer_invoice_id = rec.customer_invoice_ids[:1]
            rec.primary_vendor_bill_id = rec.vendor_bill_ids[:1]

    @api.depends(
        "customer_invoice_ids.amount_residual",
        "customer_invoice_ids.amount_total",
        "customer_invoice_ids.payment_state",
        "customer_invoice_ids.state",
        "vendor_bill_ids.amount_residual",
        "vendor_bill_ids.amount_total",
        "vendor_bill_ids.payment_state",
        "vendor_bill_ids.state",
        "company_currency_id",
    )
    def _compute_payment_balances(self):
        for rec in self:
            cust = rec.customer_invoice_ids.filtered(lambda m: m.state == "posted")
            vend = rec.vendor_bill_ids.filtered(lambda m: m.state == "posted")
            to_collect = sum(cust.mapped("amount_residual"))
            cust_total = sum(cust.mapped("amount_total"))
            to_pay = sum(vend.mapped("amount_residual"))
            vend_total = sum(vend.mapped("amount_total"))
            rec.amount_to_collect = to_collect
            rec.amount_to_pay = to_pay
            rec.amount_collected = max(cust_total - to_collect, 0.0)
            rec.amount_paid_vendor = max(vend_total - to_pay, 0.0)

    @api.depends(
        "sale_real_amount",
        "sale_estimated_amount",
        "cost_real_amount",
        "cost_estimated_amount",
        "real_margin",
        "estimated_margin",
        "real_margin_pct",
        "estimated_margin_pct",
        "margin_is_calculable",
    )
    def _compute_display_amounts(self):
        for rec in self:
            sale = rec.sale_real_amount or rec.sale_estimated_amount
            # Never stack estimated + real for the same coverage (e.g. OC 22,100 +
            # bill 22,100 → 44,200). Prefer real; if estimated is higher (pending
            # bill), keep committed ceiling via max(est, real).
            est = rec.cost_estimated_amount or 0.0
            real = rec.cost_real_amount or 0.0
            if float_compare(real, 0.0, precision_digits=2) > 0:
                cost = max(est, real)
            else:
                cost = est
            rec.display_sale_amount = sale
            rec.display_cost_amount = cost
            if rec.margin_is_calculable and real:
                rec.display_margin_amount = (sale or 0.0) - cost
                rec.display_margin_pct = (
                    (rec.display_margin_amount / sale * 100.0) if sale else 0.0
                )
            else:
                rec.display_margin_amount = rec.estimated_margin
                rec.display_margin_pct = rec.estimated_margin_pct

    @api.depends(
        "line_ids.amount_untaxed",
        "line_ids.line_type",
        "line_ids.purchase_order_line_id",
        "line_ids.state",
        "line_ids.exclude_from_margin",
    )
    def _compute_invalid_cost_alert(self):
        for rec in self:
            bad = rec.line_ids.filtered(
                lambda l: l.line_type == "cost"
                and l.state != "excluded"
                and not l.exclude_from_margin
                and l.purchase_order_line_id
                and float_is_zero(l.amount_untaxed, precision_digits=2)
                and float_compare(
                    l.purchase_order_line_id.price_subtotal, 0.0, precision_digits=2
                )
                > 0
            )
            if bad:
                names = ", ".join(
                    bad.mapped(
                        lambda l: l.product_id.display_name
                        or l.description
                        or l.purchase_order_id.name
                        or _("línea")
                    )
                )
                rec.invalid_cost_alert = _(
                    "La línea de compra no tiene costo válido: %s. "
                    "Revise el precio de la orden de compra o pulse «Recalcular costos»."
                ) % names
            else:
                rec.invalid_cost_alert = False

    @api.depends(
        "state",
        "approval_state",
        "validation_state",
        "source",
        "sale_without_cost",
        "has_related_sale",
        "has_related_cost",
        "customer_invoice_ids",
        "vendor_bill_ids",
        "purchase_order_ids",
        "sale_order_ids",
        "cost_estimated_amount",
        "cost_real_amount",
        "sale_estimated_amount",
        "sale_real_amount",
        "primary_sale_order_id",
        "primary_purchase_order_id",
        "cost_coverage_state",
        "cost_pending_sale_qty",
    )
    def _compute_ux_guidance(self):
        for rec in self:
            rec._assign_ux_guidance()

    @api.depends(
        "cost_coverage_state",
        "cost_pending_sale_qty",
        "has_related_cost",
        "has_related_sale",
        "vendor_bill_ids",
        "company_currency_id",
    )
    def _compute_commercial_cost_status(self):
        icons = {
            "pending": "🔴",
            "partial": "🟠",
            "linked": "🟢",
            "confirmed": "🟢",
        }
        for rec in self:
            tx = rec.sudo()
            coverage = tx.cost_coverage_state or "n_a"
            pending_qty = tx.cost_pending_sale_qty or 0.0
            has_real = float_compare(tx.cost_real_amount or 0.0, 0.0, precision_digits=2) > 0
            has_bills = bool(tx.vendor_bill_ids)

            if coverage == "complete" and (has_real or has_bills):
                status = "confirmed"
            elif coverage == "complete":
                status = "linked"
            elif coverage == "partial" or (
                float_compare(pending_qty, 0.0, precision_digits=4) > 0
                and rec.has_related_cost
            ):
                status = "partial"
            elif rec.has_related_sale and not rec.has_related_cost:
                status = "pending"
            elif float_compare(pending_qty, 0.0, precision_digits=4) > 0:
                status = "pending"
            else:
                status = "linked" if tx.has_related_cost else "pending"

            label = dict(COMMERCIAL_COST_STATUS).get(status, status)
            rec.commercial_cost_status = status
            rec.commercial_cost_status_label = "%s %s" % (icons.get(status, ""), label)
            rec.show_legacy_pending_banner = status in ("pending", "partial")

            if status == "linked":
                cost_amt = tx.cost_estimated_amount or tx.cost_real_amount or 0.0
                currency = tx.company_currency_id or rec.env.company.currency_id
                cost_txt = currency.format(cost_amt) if currency else "%.2f" % cost_amt
                rec.cost_status_compact_html = Markup(
                    "<div class='alert alert-success py-2 px-3 mb-2'>"
                    "<strong>%s Costos relacionados</strong><br/>"
                    "Costo estimado: %s<br/>"
                    "Factura proveedor: <em>Pendiente</em>"
                    "</div>"
                ) % (escape(icons["linked"]), escape(cost_txt))
            elif status == "confirmed":
                cost_amt = tx.cost_real_amount or tx.cost_estimated_amount or 0.0
                currency = tx.company_currency_id or rec.env.company.currency_id
                cost_txt = currency.format(cost_amt) if currency else "%.2f" % cost_amt
                rec.cost_status_compact_html = Markup(
                    "<div class='alert alert-success py-2 px-3 mb-2'>"
                    "<strong>%s Costos reales confirmados</strong><br/>"
                    "Costo real: %s"
                    "</div>"
                ) % (escape(icons["confirmed"]), escape(cost_txt))
            else:
                rec.cost_status_compact_html = False

    def _assign_ux_guidance(self):
        self.ensure_one()
        so = self.primary_sale_order_id.name if self.primary_sale_order_id else False
        po = self.primary_purchase_order_id.name if self.primary_purchase_order_id else False
        sale_amt = self.sale_real_amount or self.sale_estimated_amount or 0.0

        if self.state == "rejected":
            self.business_state = "rejected"
            self.business_state_help = _(
                "La operación fue rechazada. Revise el motivo en el historial y corrija o reabra."
            )
            self.pending_reason = _("La operación está rechazada.")
            self.pending_action = _("Reabrir o corregir")
            self.pending_actor = "purchases"
            self.pending_action_banner = _(
                "Acción pendiente: Compras o Finanzas deben corregir y reabrir la operación."
            )
            return

        if self.state == "closed":
            self.business_state = "closed"
            self.business_state_help = _("Operación cerrada. Solo lectura operativa.")
            self.pending_reason = False
            self.pending_action = False
            self.pending_actor = "none"
            self.pending_action_banner = False
            return

        if self.state == "approved":
            self.business_state = "approved"
            self.business_state_help = _(
                "Finanzas ya aprobó el margen. Puede cerrar la operación cuando cobros y pagos estén al día."
            )
            self.pending_reason = _("Lista para cierre operativo.")
            self.pending_action = _("Cerrar operación")
            self.pending_actor = "finance"
            self.pending_action_banner = _(
                "Acción pendiente: Finanzas puede cerrar la operación cuando corresponda."
            )
            return

        if self.state == "validated" or self.approval_state == "pending":
            margin = self.display_margin_amount
            if margin is None:
                margin = (self.display_sale_amount or sale_amt or 0.0) - (
                    self.display_cost_amount or self.cost_estimated_amount or 0.0
                )
            needs_finance = self.approval_state == "pending" or float_compare(
                margin or 0.0, 0.0, precision_digits=2
            ) < 0
            if not needs_finance and self.approval_state in (
                "not_requested",
                False,
                None,
            ):
                # Normal fully-covered sale: costs confirmed, no Finance gate.
                self.business_state = "purchase_validated"
                self.business_state_help = _(
                    "Costos confirmados automáticamente (cobertura completa). "
                    "No requiere aprobación de Finanzas."
                )
                self.pending_reason = False
                self.pending_action = False
                self.pending_actor = "none"
                self.pending_action_banner = False
                return
            self.business_state = "finance_pending"
            self.business_state_help = _(
                "Hay una excepción o solicitud de Finanzas. Confirme venta, costo, margen y saldos."
            )
            self.pending_reason = _(
                "Falta la aprobación de Finanzas (venta %(sale)s · costo %(cost)s · margen %(margin)s)."
            ) % {
                "sale": self.display_sale_amount or sale_amt,
                "cost": self.display_cost_amount or self.cost_estimated_amount,
                "margin": self.display_margin_amount or self.estimated_margin,
            }
            self.pending_action = _("Aprobar operación")
            self.pending_actor = "finance"
            self.pending_action_banner = _(
                "Acción pendiente: Finanzas debe aprobar el margen de esta operación."
            )
            return

        if self.state == "pending_review":
            self.business_state = "to_review"
            self.business_state_help = _(
                "Compras debe confirmar proveedor, artículos, costo y venta relacionada."
            )
            self.pending_reason = _(
                "Pendiente de revisión de Compras: verificar que el costo corresponde a la venta."
            )
            self.pending_action = _("Validar relación")
            self.pending_actor = "purchases"
            detail = ""
            if po and so:
                detail = _(" Confirme si %(po)s corresponde a %(so)s.") % {"po": po, "so": so}
            self.pending_action_banner = _(
                "Acción pendiente: Compras debe validar la relación.%s"
            ) % detail
            return

        if self.has_related_sale and not self.has_related_cost:
            self.business_state = "need_relation"
            self.business_state_help = _(
                "Hay venta, pero todavía no hay órdenes de compra ni facturas de proveedor vinculadas."
            )
            self.pending_reason = _(
                "La venta tiene %(amount)s facturados/comprometidos, pero no tiene costos asociados."
            ) % {"amount": sale_amt}
            self.pending_action = _("Agregar costos")
            self.pending_actor = "purchases"
            self.pending_action_banner = _(
                "Acción pendiente: Compras debe agregar órdenes de compra o facturas de proveedor."
            )
            return

        if self.has_related_cost and not self.has_related_sale:
            self.business_state = "need_relation"
            self.business_state_help = _(
                "Hay compra, pero todavía no está vinculada a una venta o factura de cliente."
            )
            self.pending_reason = _(
                "Falta seleccionar la factura de venta o la orden de venta relacionada."
            )
            self.pending_action = _("Relacionar con venta")
            self.pending_actor = "purchases"
            self.pending_action_banner = _(
                "Acción pendiente: Compras debe relacionar esta compra con una venta."
            )
            return

        if self.source in ("backfill", "auto_detected", "cost_link") and self.state in (
            "draft",
            "detected",
        ):
            self.business_state = "suggested"
            self.business_state_help = _(
                "El sistema propuso esta relación a partir de documentos históricos. Debe revisarse."
            )
            self.pending_reason = _("Relación sugerida pendiente de confirmación.")
            self.pending_action = _("Revisar")
            self.pending_actor = "purchases"
            if po and so:
                self.pending_action_banner = _(
                    "Acción pendiente: Compras debe confirmar si %(po)s corresponde a %(so)s."
                ) % {"po": po, "so": so}
            else:
                self.pending_action_banner = _(
                    "Acción pendiente: Compras debe revisar la relación sugerida."
                )
            return

        if (
            self.has_related_sale
            and self.purchase_order_ids
            and not self.vendor_bill_ids
            and not self.cost_real_amount
        ):
            if getattr(self, "cost_coverage_state", False) == "complete":
                self.business_state = "purchase_validated"
                self.business_state_help = _(
                    "Cobertura comercial completa. Falta factura de proveedor para costo real."
                )
                self.pending_reason = False
                self.pending_action = _("Agregar factura de proveedor")
                self.pending_actor = "purchases"
                self.pending_action_banner = False
                return
            self.business_state = "need_vendor_bill"
            self.business_state_help = _(
                "Hay orden(es) de compra, pero aún no hay factura de proveedor registrada como costo real."
            )
            self.pending_reason = _(
                "Falta la factura del proveedor para convertir el costo estimado en costo real."
            )
            self.pending_action = _("Registrar factura proveedor")
            self.pending_actor = "purchases"
            self.pending_action_banner = _(
                "Acción pendiente: Compras debe registrar o vincular la factura del proveedor."
            )
            return

        if self.sale_order_ids and not self.customer_invoice_ids and not self.sale_real_amount:
            self.business_state = "need_customer_invoice"
            self.business_state_help = _(
                "Hay orden de venta, pero todavía no hay factura de cliente contabilizada."
            )
            self.pending_reason = _("Falta la factura del cliente.")
            self.pending_action = _("Facturar al cliente")
            self.pending_actor = "sales"
            self.pending_action_banner = _(
                "Acción pendiente: Ventas debe emitir la factura de cliente."
            )
            return

        self.business_state = "to_review"
        self.business_state_help = _("Operación detectada o en borrador; requiere revisión.")
        self.pending_reason = _("Falta enviar a revisión o completar documentos.")
        self.pending_action = _("Enviar a revisión")
        self.pending_actor = "purchases"
        self.pending_action_banner = _(
            "Acción pendiente: Compras debe revisar y enviar a validación."
        )

    # ------------------------------------------------------------------
    # Acciones de bandeja (sin abrir formularios técnicos)
    # ------------------------------------------------------------------
    def action_inbox_relate(self):
        self.ensure_one()
        if self.has_related_cost and not self.has_related_sale:
            return {
                "type": "ir.actions.act_window",
                "name": _("Relacionar documentos"),
                "res_model": "purchase.sale.relate.documents.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_company_id": self.company_id.id,
                    "default_transaction_id": self.id,
                    "default_vendor_bill_id": self.primary_vendor_bill_id.id,
                },
            }
        return self.action_add_purchase_orders()

    def action_inbox_review(self):
        self.ensure_one()
        if self.state in ("draft", "detected", "reopened"):
            self.action_send_review()
        return self.get_formview_action()

    def action_inbox_approve(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Aprobar operación"),
            "res_model": "purchase.sale.approve.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_transaction_id": self.id},
        }

    def action_inbox_validate(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Validar relación"),
            "res_model": "purchase.sale.validate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_transaction_id": self.id},
        }

    def action_inbox_correct(self):
        return self.get_formview_action()

    def action_inbox_exclude(self):
        self.ensure_one()
        self.write({"active": False})
        self.message_post(
            body=_(
                "%(user)s excluyó esta operación de las bandejas de trabajo el %(date)s."
            )
            % {"user": self.env.user.display_name, "date": fields.Datetime.now()}
        )
        return True

    def action_view_operation(self):
        return self.get_formview_action()

    def action_add_vendor_bills(self):
        """Open multi-PO/cost wizard focused on vendor bills."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar factura de proveedor"),
            "res_model": "purchase.sale.add.purchase.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_transaction_id": self.id,
                "default_company_id": self.company_id.id,
                "default_partner_id": self.primary_supplier_id.id,
            },
        }

    def action_recompute_costs(self):
        """Extiende el recálculo para reparar costos en cero con precio de OC."""
        self._repair_zero_cost_lines()
        return super().action_recompute_costs()

    def _repair_zero_cost_lines(self):
        for rec in self:
            for line in rec.line_ids.filtered(
                lambda l: l.line_type == "cost"
                and l.purchase_order_line_id
                and float_is_zero(l.amount_untaxed, precision_digits=2)
            ):
                pol = line.purchase_order_line_id
                if float_is_zero(pol.price_subtotal, precision_digits=2):
                    continue
                qty = line.quantity or pol.product_qty or 0.0
                ratio = (qty / pol.product_qty) if pol.product_qty else 1.0
                line.write(
                    {
                        "amount_untaxed": pol.price_subtotal * ratio,
                        "amount_tax": pol.price_tax * ratio,
                        "amount_total": pol.price_total * ratio,
                        "currency_id": pol.currency_id.id or pol.order_id.currency_id.id,
                    }
                )
        return True

    # ------------------------------------------------------------------
    # Workflow con mensajes en lenguaje natural
    # ------------------------------------------------------------------
    def action_send_review(self):
        res = super().action_send_review()
        for rec in self:
            rec.message_post(
                body=_(
                    "%(user)s envió la operación a revisión de Compras "
                    "(venta %(sale)s · costo %(cost)s)."
                )
                % {
                    "user": self.env.user.display_name,
                    "sale": rec.display_sale_amount,
                    "cost": rec.display_cost_amount,
                }
            )
        return res

    def action_validate_costs(self):
        res = super().action_validate_costs()
        for rec in self:
            rec.message_post(
                body=_(
                    "Compras validó la relación por %(cost)s "
                    "(venta %(sale)s · margen estimado %(margin)s)."
                )
                % {
                    "cost": rec.display_cost_amount,
                    "sale": rec.display_sale_amount,
                    "margin": rec.estimated_margin,
                }
            )
        return res

    def action_approve(self):
        res = super().action_approve()
        for rec in self:
            pct = ("%.2f" % rec.real_margin_pct) if rec.margin_is_calculable else ("%.2f" % rec.estimated_margin_pct)
            rec.message_post(
                body=_(
                    "Finanzas aprobó el margen de %(margin)s, equivalente a %(pct)s %%."
                )
                % {"margin": rec.display_margin_amount, "pct": pct}
            )
        return res

    def action_reject(self):
        res = super().action_reject()
        for rec in self:
            rec.message_post(
                body=_(
                    "La relación fue rechazada. Revise artículos, proveedor y venta antes de reabrir."
                )
            )
        return res
