# -*- coding: utf-8 -*-
"""19.0.8.0.0 — Clasificación de relación + UAT + unicidad factura proveedor."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero


class PurchaseSaleMarginTransactionSprint6(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    is_uat_fixture = fields.Boolean(
        string="Fixture UAT",
        default=False,
        index=True,
        help="Marca datos de prueba para limpieza segura.",
    )
    project_name = fields.Char(string="Proyecto / referencia")
    quotation_ids = fields.Many2many(
        "sale.order",
        "psm_tx_quotation_rel",
        "transaction_id",
        "sale_order_id",
        string="Cotizaciones",
    )
    report_relation_class = fields.Selection(
        [
            ("complete", "Completa"),
            ("partial_with_cost", "Parcial con costos"),
            ("sale_without_cost", "Venta sin costos"),
            ("pending_relation", "Pendiente de relacionar"),
            ("incomplete_historical", "Histórica incompleta"),
            ("probable_duplicate", "Duplicada probable"),
        ],
        string="Clase de relación (reporte)",
        compute="_compute_report_relation_class",
        store=True,
        index=True,
    )

    @api.depends(
        "sale_order_ids",
        "purchase_order_ids",
        "customer_invoice_ids",
        "vendor_bill_ids",
        "cost_real_amount",
        "cost_estimated_amount",
        "sale_real_amount",
        "sale_estimated_amount",
        "state",
    )
    def _compute_report_relation_class(self):
        for tx in self:
            has_sale = bool(tx.sale_order_ids or tx.customer_invoice_ids)
            has_cost_docs = bool(tx.purchase_order_ids or tx.vendor_bill_ids)
            cost_amt = (tx.cost_real_amount or 0.0) + (tx.cost_estimated_amount or 0.0)
            has_cost_amt = not float_is_zero(cost_amt, precision_digits=2)
            if has_sale and has_cost_docs and has_cost_amt:
                if tx.vendor_bill_ids and (tx.customer_invoice_ids or tx.sale_order_ids):
                    tx.report_relation_class = "complete"
                else:
                    tx.report_relation_class = "partial_with_cost"
            elif has_sale and not has_cost_docs and not has_cost_amt:
                tx.report_relation_class = "sale_without_cost"
            elif has_cost_docs and not has_sale:
                tx.report_relation_class = "incomplete_historical"
            elif has_sale and not has_cost_amt:
                tx.report_relation_class = "pending_relation"
            else:
                tx.report_relation_class = "incomplete_historical"

    def _is_report_main_eligible(self):
        """Default Excel/PDF: only useful cost relations."""
        self.ensure_one()
        return self.report_relation_class in ("complete", "partial_with_cost")

    @api.constrains("vendor_bill_ids")
    def _check_vendor_bill_unique_transaction(self):
        if self.env.context.get("skip_vendor_bill_unique"):
            return
        Rel = self.env["purchase.sale.margin.transaction"]
        for tx in self:
            for bill in tx.vendor_bill_ids:
                others = Rel.search(
                    [
                        ("id", "!=", tx.id),
                        ("is_merged", "=", False),
                        ("vendor_bill_ids", "in", bill.id),
                    ],
                    limit=1,
                )
                if others:
                    raise ValidationError(
                        _(
                            "La factura de proveedor %(bill)s ya pertenece a la "
                            "transacción %(tx)s. No puede asignarse a %(current)s."
                        )
                        % {
                            "bill": bill.display_name,
                            "tx": others.transaction_number or others.display_name,
                            "current": tx.transaction_number or tx.display_name,
                        }
                    )
