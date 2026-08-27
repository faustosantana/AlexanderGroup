# -*- coding: utf-8 -*-
"""19.0.4.0.0 — Dashboard profesional con textos explicativos y drill-down."""
from odoo import _, api, fields, models


class PurchaseSaleMarginBoardUX(models.TransientModel):
    _inherit = "purchase.sale.margin.board"

    related_costs_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Costos relacionados"
    )
    amount_to_collect_total = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Cuentas por cobrar"
    )
    amount_to_pay_total = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Cuentas por pagar"
    )
    suggested_relation_count = fields.Integer(readonly=True, string="Relaciones por revisar")
    ready_to_close_count = fields.Integer(readonly=True, string="Listas para cerrar")
    net_cash_flow = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Flujo neto"
    )
    kpi_sales_help = fields.Char(
        readonly=True,
        default=lambda self: _(
            "Ventas reales contables: facturas posted − NC posted (amount_untaxed_signed). No depende de MTX."
        ),
    )
    kpi_costs_help = fields.Char(readonly=True, default=lambda self: _("Costos estimados o reales ya vinculados a operaciones."))
    kpi_margin_help = fields.Char(
        readonly=True,
        default=lambda self: _(
            "Relaciones Venta↔Costo confirmadas. Costo: Bill real si existe; si no, PO comprometido."
        ),
    )
    kpi_collect_help = fields.Char(
        readonly=True,
        default=lambda self: _("Cuentas por cobrar al corte: residual receivable posted. Independiente de MTX."),
    )
    kpi_pay_help = fields.Char(
        readonly=True,
        default=lambda self: _("Cuentas por pagar al corte: residual payable posted. Independiente de MTX."),
    )
    kpi_sales_no_cost_help = fields.Char(readonly=True, default=lambda self: _("Ventas que todavía no tienen facturas de proveedor u OC relacionadas."))
    kpi_purchases_no_sale_help = fields.Char(readonly=True, default=lambda self: _("Compras que aún no están vinculadas a una venta o factura de cliente."))
    kpi_suggested_help = fields.Char(readonly=True, default=lambda self: _("Relaciones propuestas por el sistema que Compras debe confirmar."))
    kpi_approval_help = fields.Char(readonly=True, default=lambda self: _("Operaciones validadas por Compras que esperan aprobación de Finanzas."))
    kpi_negative_help = fields.Char(readonly=True, default=lambda self: _("Operaciones con margen real negativo; requieren revisión."))

    def _compute_kpis(self, companies, date_from=None, date_to=None):
        vals = super()._compute_kpis(companies, date_from=date_from, date_to=date_to)
        Transaction = self.env["purchase.sale.margin.transaction"]
        domain = [("company_id", "in", companies.ids)]
        if date_from:
            domain.append(("transaction_date", ">=", date_from))
        if date_to:
            domain.append(("transaction_date", "<=", date_to))
        all_tx = Transaction.search(domain)
        related_costs = sum(
            (t.cost_real_amount or t.cost_estimated_amount) for t in all_tx.filtered("has_related_cost")
        )
        vals.update(
            {
                "related_costs_amount": related_costs,
                "suggested_relation_count": len(
                    all_tx.filtered(lambda t: t.business_state == "suggested")
                ),
                "ready_to_close_count": len(all_tx.filtered(lambda t: t.state == "approved")),
                "kpi_sales_help": _(
                    "Ventas reales contables (posted FC − NC). %s facturas · %s NC. "
                    "Independiente de MTX."
                )
                % (vals.get("total_sales_count", 0), vals.get("posted_credit_note_count", 0)),
                "kpi_costs_help": _("Costos estimados o reales ya vinculados a operaciones."),
                "kpi_margin_help": _(
                    "Relaciones Venta↔Costo confirmadas (%s ops). "
                    "Costo: Vendor Bill real si existe; si no, costo comprometido de PO. No suma PO+Bill."
                )
                % len(
                    all_tx.filtered(
                        lambda t: t.state in ("validated", "approved", "closed")
                        and t.transaction_type != "administrative"
                        and not t.sale_without_cost
                        and t.has_related_sale
                        and t.has_related_cost
                    )
                ),
                "kpi_sales_no_cost_help": _(
                    "%s facturas/operaciones · ventas sin costos relacionados (incluye posted sin MTX)."
                )
                % vals.get("sales_without_cost_count", 0),
                "kpi_purchases_no_sale_help": _(
                    "%s compras · todavía sin venta o factura de cliente."
                )
                % vals.get("purchases_without_sale_count", 0),
                "kpi_suggested_help": _(
                    "Relaciones propuestas por el sistema que Compras debe confirmar."
                ),
                "kpi_approval_help": _(
                    "Operaciones validadas por Compras que esperan aprobación de Finanzas."
                ),
                "kpi_negative_help": _(
                    "Operaciones con margen real negativo; requieren revisión."
                ),
            }
        )
        return vals

    def action_open_suggested_relations(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Relaciones por revisar"),
            self._domain_base(companies) + [("business_state", "=", "suggested")],
        )

    def action_open_amount_to_collect(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Pendiente de cobro"),
            self._domain_base(companies) + [("amount_to_collect", ">", 0)],
        )

    def action_open_amount_to_pay(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Pendiente de pago"),
            self._domain_base(companies) + [("amount_to_pay", ">", 0)],
        )

    def action_open_related_costs(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Costos relacionados"),
            self._domain_base(companies) + [("has_related_cost", "=", True)],
        )

    def action_open_ready_to_close(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Operaciones listas para cerrar"),
            self._domain_base(companies) + [("state", "=", "approved")],
        )
