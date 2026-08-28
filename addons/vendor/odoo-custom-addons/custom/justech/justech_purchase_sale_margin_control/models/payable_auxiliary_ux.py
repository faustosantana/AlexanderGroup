# -*- coding: utf-8 -*-
"""19.0.4.0.0 — Etiquetas y ayuda UX del auxiliar CxP."""
from odoo import _, api, fields, models


class PurchaseSalePayableAuxiliaryUX(models.Model):
    _inherit = "purchase.sale.payable.auxiliary"

    relation_status_label = fields.Char(
        string="Estado de relación",
        compute="_compute_ux_labels",
        store=True,
    )
    what_is_missing = fields.Text(
        string="¿Qué falta?",
        compute="_compute_ux_labels",
        store=True,
    )
    related_customer_id = fields.Many2one(
        "res.partner",
        string="Cliente relacionado",
        compute="_compute_ux_labels",
        store=True,
    )
    related_customer_invoice_id = fields.Many2one(
        "account.move",
        string="Factura cliente relacionada",
        compute="_compute_ux_labels",
        store=True,
    )
    related_sale_order_id = fields.Many2one(
        "sale.order",
        string="Venta relacionada",
        compute="_compute_ux_labels",
        store=True,
    )
    amount_paid = fields.Monetary(
        string="Pagado",
        compute="_compute_amount_paid",
        currency_field="currency_id",
    )

    @api.depends("amount_total", "amount_residual")
    def _compute_amount_paid(self):
        for rec in self:
            rec.amount_paid = max((rec.amount_total or 0.0) - (rec.amount_residual or 0.0), 0.0)

    @api.depends(
        "operational_state",
        "transaction_ids",
        "sale_order_ids",
        "customer_invoice_ids",
        "recovery_percent",
        "pending_recovery_amount",
        "amount_residual",
        "partner_id",
    )
    def _compute_ux_labels(self):
        labels = {
            "pending_relation": _("Sin venta relacionada"),
            "partial_relation": _("Parcialmente relacionada"),
            "full_relation": _("Totalmente relacionada"),
            "invoiced_to_customer": _("Recuperada mediante venta"),
            "pending_customer_collection": _("Pendiente de recuperar (cobro cliente)"),
            "pending_vendor_payment": _("Pendiente de pagar"),
            "partial_paid": _("Pagada parcialmente"),
            "paid": _("Pagada"),
            "closed": _("Cerrada"),
        }
        helps = {
            "pending_relation": _(
                "Esta factura de proveedor todavía no está vinculada a una venta o factura de cliente. "
                "Seleccione la operación comercial correspondiente."
            ),
            "partial_relation": _(
                "La factura está parcialmente relacionada. Revise el costo pendiente de recuperar."
            ),
            "full_relation": _("La compra ya está relacionada con venta(s)."),
            "invoiced_to_customer": _("El costo ya tiene factura de cliente asociada."),
            "pending_customer_collection": _(
                "El costo está relacionado, pero el cliente aún tiene saldo pendiente de cobro."
            ),
            "pending_vendor_payment": _("La factura del proveedor aún tiene saldo por pagar."),
            "partial_paid": _("La factura del proveedor está pagada parcialmente."),
            "paid": _("La factura del proveedor está pagada."),
            "closed": _("Registro cerrado operativamente."),
        }
        for rec in self:
            rec.relation_status_label = labels.get(rec.operational_state, rec.operational_state)
            rec.what_is_missing = helps.get(rec.operational_state, False)
            rec.related_sale_order_id = rec.sale_order_ids[:1] or (
                rec.transaction_ids[:1].primary_sale_order_id if rec.transaction_ids else False
            )
            rec.related_customer_invoice_id = rec.customer_invoice_ids[:1] or (
                rec.transaction_ids[:1].primary_customer_invoice_id if rec.transaction_ids else False
            )
            cust = False
            if rec.related_customer_invoice_id:
                cust = rec.related_customer_invoice_id.partner_id
            elif rec.related_sale_order_id:
                cust = rec.related_sale_order_id.partner_id
            elif rec.transaction_ids:
                cust = rec.transaction_ids[:1].customer_id
            rec.related_customer_id = cust
