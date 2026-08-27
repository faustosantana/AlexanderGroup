# -*- coding: utf-8 -*-
"""19.0.5.0.0 — Corrección de fórmulas financieras y próxima acción."""
from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero

NEXT_ACTIONS = [
    ("add_costs", "Compras debe agregar costos"),
    ("validate_relation", "Compras debe validar la relación"),
    ("approve_finance", "Finanzas debe aprobar"),
    ("wait_vendor_bill", "Esperando factura del proveedor"),
    ("wait_customer_invoice", "Esperando factura del cliente"),
    ("wait_vendor_payment", "Esperando pago al proveedor"),
    ("wait_customer_payment", "Esperando cobro del cliente"),
    ("fix_difference", "Corregir diferencia"),
    ("ready_to_close", "Operación lista para cerrar"),
    ("closed", "Operación cerrada"),
    ("none", "Sin acción"),
]

MARGIN_BANDS = [
    ("healthy", "Saludable"),
    ("low", "Bajo"),
    ("negative", "Negativo"),
    ("pending", "Pendiente / no calculable"),
]


class PurchaseSaleMarginTransactionFinanceFix(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    next_action = fields.Selection(
        NEXT_ACTIONS,
        string="Próxima acción",
        compute="_compute_next_action",
        store=True,
        index=True,
    )
    margin_band = fields.Selection(
        MARGIN_BANDS,
        string="Clasificación de margen",
        compute="_compute_margin_band",
        store=True,
        index=True,
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    coverage_available = fields.Boolean(
        string="Cobertura disponible",
        compute="_compute_amounts",
        store=True,
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    coverage_display = fields.Char(
        string="Cobertura",
        compute="_compute_coverage_display",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )

    @api.depends(
        "line_ids.line_type",
        "line_ids.data_origin",
        "line_ids.amount_company_currency",
        "line_ids.exclude_from_margin",
        "line_ids.cost_usage_type",
        "line_ids.state",
        "line_ids.purchase_order_id",
        "line_ids.purchase_order_id.state",
        "line_ids.account_move_id",
        "line_ids.account_move_id.state",
        "purchase_order_ids.state",
    )
    def _compute_amounts(self):
        """Override: margen real coherente, cobertura acotada, sin 10000 %.

        Never count cost lines whose purchase order or vendor bill is cancelled.
        That was the root cause of double-counting cancelled draft POs.
        """
        for rec in self:
            def _line_live(line):
                if line.state == "excluded" or line.exclude_from_margin:
                    return False
                po = line.purchase_order_id
                if po and po.state == "cancel":
                    return False
                am = line.account_move_id
                if am and am.state == "cancel":
                    return False
                return True

            active_lines = rec.line_ids.filtered(_line_live)
            sale_lines = active_lines.filtered(lambda l: l.line_type == "sale")
            cost_lines = active_lines.filtered(lambda l: l.line_type == "cost")

            real_cost_lines = cost_lines.filtered(lambda l: l.data_origin == "accounting")
            inv_est_lines = cost_lines.filtered(
                lambda l: l.cost_source in ("inventory", "manual")
                and l.data_origin != "accounting"
            )
            margin_cost_lines = real_cost_lines.filtered(
                lambda l: l.cost_usage_type != "administrative_expense"
            )
            admin_cost_lines = real_cost_lines.filtered(
                lambda l: l.cost_usage_type == "administrative_expense"
            )
            additional_cost_lines = real_cost_lines.filtered(
                lambda l: l.cost_usage_type in ("logistic", "financial", "other")
            )

            sale_estimated = sum(
                sale_lines.filtered(lambda l: l.data_origin == "estimated").mapped(
                    "amount_company_currency"
                )
            )
            sale_real = sum(
                sale_lines.filtered(lambda l: l.data_origin in ("accounting", "manual")).mapped(
                    "amount_company_currency"
                )
            )
            cost_estimated = sum(
                cost_lines.filtered(lambda l: l.data_origin == "estimated").mapped(
                    "amount_company_currency"
                )
            ) + sum(inv_est_lines.mapped("amount_company_currency"))
            cost_real = sum(margin_cost_lines.mapped("amount_company_currency"))
            additional_cost = sum(additional_cost_lines.mapped("amount_company_currency"))

            if float_is_zero(sale_estimated, precision_digits=2):
                sale_estimated = sale_real
            if float_is_zero(cost_estimated, precision_digits=2):
                cost_estimated = cost_real

            rec.sale_estimated_amount = sale_estimated
            rec.sale_real_amount = sale_real
            rec.cost_estimated_amount = cost_estimated
            rec.cost_real_amount = cost_real
            rec.additional_cost_amount = additional_cost
            rec.pending_cost_amount = max(cost_estimated - cost_real, 0.0)
            rec.pending_sale_amount = max(sale_estimated - sale_real, 0.0)

            rec.estimated_margin = sale_estimated - cost_estimated
            rec.estimated_margin_pct = (
                (rec.estimated_margin / sale_estimated * 100.0) if sale_estimated else 0.0
            )

            has_sale_side = not float_is_zero(sale_real, precision_digits=2) or not float_is_zero(
                sale_estimated, precision_digits=2
            )
            has_real_cost = bool(margin_cost_lines) or bool(admin_cost_lines)

            # Real margin only when there is a sale base AND cost (or admin).
            # Cost-only must never appear as "negative margin = -cost".
            if has_real_cost and not float_is_zero(sale_real, precision_digits=2):
                rec.real_margin = sale_real - cost_real
                rec.real_margin_pct = rec.real_margin / sale_real * 100.0
            elif has_real_cost and not float_is_zero(sale_estimated, precision_digits=2) and float_is_zero(
                sale_real, precision_digits=2
            ):
                # Use estimated sale until customer invoice exists (working margin).
                rec.real_margin = sale_estimated - cost_real
                rec.real_margin_pct = rec.real_margin / sale_estimated * 100.0
            else:
                rec.real_margin = 0.0
                rec.real_margin_pct = 0.0

            # Coverage: related cost / expected cost. Cap absurd ratios; N/A if no expected.
            if float_is_zero(cost_estimated, precision_digits=2):
                rec.coverage_percent = 0.0
                rec.coverage_available = False
            else:
                raw = cost_real / cost_estimated * 100.0 if cost_real else 0.0
                # If only estimated costs exist, coverage of commitment vs itself = 0 until bill.
                if float_is_zero(cost_real, precision_digits=2) and cost_estimated:
                    raw = 0.0
                rec.coverage_percent = min(max(raw, 0.0), 100.0)
                rec.coverage_available = True

    @api.depends("coverage_available", "coverage_percent", "cost_estimated_amount", "cost_real_amount")
    def _compute_coverage_display(self):
        for rec in self:
            if not rec.coverage_available or float_is_zero(rec.cost_estimated_amount, precision_digits=2):
                rec.coverage_display = _("No disponible")
            elif float_is_zero(rec.cost_real_amount, precision_digits=2):
                rec.coverage_display = _("Pendiente")
            else:
                rec.coverage_display = "%.1f %%" % rec.coverage_percent

    @api.depends(
        "sale_real_amount",
        "sale_estimated_amount",
        "cost_real_amount",
        "cost_estimated_amount",
        "has_related_sale",
        "has_related_cost",
        "sale_without_cost",
    )
    def _compute_display_amounts(self):
        for rec in self:
            sale = rec.sale_real_amount or rec.sale_estimated_amount
            est = rec.cost_estimated_amount or 0.0
            real = rec.cost_real_amount or 0.0
            # Do not double-count estimated+real (same economic cost twice).
            if float_compare(real, 0.0, precision_digits=2) > 0:
                cost = max(est, real)
            else:
                cost = est
            rec.display_sale_amount = sale
            rec.display_cost_amount = cost

            if not rec.has_related_sale and rec.has_related_cost:
                # Compra sin venta: margen no calculable (no mostrar -costo).
                rec.display_margin_amount = 0.0
                rec.display_margin_pct = 0.0
            elif rec.sale_without_cost or (sale and float_is_zero(cost, precision_digits=2)):
                rec.display_margin_amount = 0.0
                rec.display_margin_pct = 0.0
            elif sale:
                margin = sale - cost
                rec.display_margin_amount = margin
                rec.display_margin_pct = margin / sale * 100.0
            else:
                rec.display_margin_amount = 0.0
                rec.display_margin_pct = 0.0

    @api.depends(
        "sale_real_amount",
        "sale_estimated_amount",
        "cost_real_amount",
        "cost_estimated_amount",
        "has_related_sale",
        "has_related_cost",
        "sale_without_cost",
    )
    def _compute_margin_band(self):
        for rec in self:
            sale = rec.sale_real_amount or rec.sale_estimated_amount
            cost = rec.cost_real_amount or rec.cost_estimated_amount
            if not rec.has_related_sale and rec.has_related_cost:
                rec.margin_band = "pending"
            elif rec.sale_without_cost or (sale and float_is_zero(cost, precision_digits=2)):
                rec.margin_band = "pending"
            elif sale:
                margin = sale - cost
                pct = margin / sale * 100.0
                if margin < 0:
                    rec.margin_band = "negative"
                elif pct < 15.0:
                    rec.margin_band = "low"
                else:
                    rec.margin_band = "healthy"
            else:
                rec.margin_band = "pending"

    @api.depends(
        "business_state",
        "state",
        "sale_without_cost",
        "has_related_sale",
        "has_related_cost",
        "amount_to_collect",
        "amount_to_pay",
        "vendor_bill_ids",
        "customer_invoice_ids",
        "purchase_order_ids",
        "cost_real_amount",
        "sale_real_amount",
    )
    def _compute_next_action(self):
        for rec in self:
            if rec.state == "closed" or rec.business_state == "closed":
                rec.next_action = "closed"
            elif rec.state == "approved" or rec.business_state == "approved":
                rec.next_action = "ready_to_close"
            elif rec.business_state == "finance_pending" or rec.approval_state == "pending":
                rec.next_action = "approve_finance"
            elif rec.business_state == "purchase_validated" or (
                rec.state == "validated" and rec.approval_state == "not_requested"
            ):
                rec.next_action = "none"
            elif rec.business_state in ("to_review", "suggested") or rec.state == "pending_review":
                rec.next_action = "validate_relation"
            elif rec.sale_without_cost or (rec.has_related_sale and not rec.has_related_cost):
                rec.next_action = "add_costs"
            elif rec.has_related_cost and not rec.has_related_sale:
                rec.next_action = "add_costs"
            elif rec.purchase_order_ids and not rec.vendor_bill_ids and float_is_zero(
                rec.cost_real_amount or 0.0, precision_digits=2
            ):
                rec.next_action = "wait_vendor_bill"
            elif rec.sale_order_ids and not rec.customer_invoice_ids and float_is_zero(
                rec.sale_real_amount or 0.0, precision_digits=2
            ):
                rec.next_action = "wait_customer_invoice"
            elif rec.amount_to_pay and float_compare(rec.amount_to_pay, 0, precision_digits=2) > 0:
                rec.next_action = "wait_vendor_payment"
            elif rec.amount_to_collect and float_compare(rec.amount_to_collect, 0, precision_digits=2) > 0:
                rec.next_action = "wait_customer_payment"
            else:
                rec.next_action = "none"