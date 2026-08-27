# -*- coding: utf-8 -*-
import logging

from odoo import _, api, models
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.models import margin_acl
from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)

_logger = logging.getLogger(__name__)


class PurchaseSaleMarginService(models.AbstractModel):
    """Canonical margin for a sale order.

    Estimated cost (no posted vendor bill):
        SUM(current POL.price_subtotal × assigned_qty / pol.qty)
        from active qty.assignment + Trace POL.sale_line_id.
        Never trust stale MTX estimated amounts if the PO changed.

    Real cost (posted vendor bill lines on MTX):
        preferred when present.
    """

    _name = "purchase.sale.margin.service"
    _description = "Servicio de cálculo de margen compra-venta"

    @api.model
    def _linked_transactions(self, sale_order):
        if not sale_order:
            return margin_acl.margin_transaction(self.env)
        Tx = margin_acl.margin_transaction(self.env)
        op = Tx._operational_domain() if hasattr(Tx, "_operational_domain") else []
        return Tx.search([("sale_order_ids", "in", sale_order.id)] + op)

    @api.model
    def _legacy_costs(self, sale_order):
        links = margin_acl.margin_cost_link(self.env).search(
            [
                ("sale_id", "=", sale_order.id),
                ("state", "!=", "cancelled"),
                ("exclude_from_sales_margin", "=", False),
            ]
        )
        estimated_cost = sum(links.mapped("committed_amount_company"))
        allocations = margin_acl.margin_cost_allocation(self.env).search(
            [
                ("sale_order_id", "=", sale_order.id),
                ("state", "in", ("confirmed", "complete", "partial")),
                ("exclude_from_sales_margin", "=", False),
                ("cost_usage_type", "!=", "administrative_expense"),
            ]
        )
        real_cost = sum(allocations.mapped("allocated_amount_company_currency"))
        unallocated_cost = sum(
            links.filtered(
                lambda l: l.allocation_status in ("unallocated", "partial")
            ).mapped(
                lambda l: max(
                    l.committed_amount_company
                    - sum(
                        l.allocation_ids.mapped("allocated_amount_company_currency")
                    ),
                    0.0,
                )
            )
        )
        return estimated_cost, real_cost, unallocated_cost

    @api.model
    def _live_estimated_from_assignments(self, sale_order):
        """Live estimated + real split from current POL prices × assigned qty."""
        rows = LineAllocationService(self.env).collect_live_assigned_cost_rows(sale_order)
        estimated = sum(r.get("estimated_cost") or 0.0 for r in rows)
        # Fallback if rows predate split fields
        if not estimated and rows and all("estimated_cost" not in r for r in rows):
            estimated = sum(r["cost"] for r in rows)
        real = sum(r.get("real_cost") or 0.0 for r in rows)
        return estimated, real, rows

    @api.model
    def _mtx_real_cost(self, txs):
        """Posted vendor-bill (accounting) cost only — never inventory/manual."""
        if not txs:
            return 0.0
        Line = margin_acl.margin_transaction_line(self.env)
        lines = Line.search(
            [
                ("transaction_id", "in", txs.ids),
                ("line_type", "=", "cost"),
                ("state", "!=", "excluded"),
                ("data_origin", "=", "accounting"),
            ]
        )
        return sum(
            lines.mapped("amount_company_currency")
            or lines.mapped("amount_untaxed")
            or [0.0]
        )

    @api.model
    def _mtx_inventory_manual_cost(self, txs):
        """Hub inventory/manual cost (not vendor-bill) — adds to estimated coverage."""
        if not txs:
            return 0.0
        Line = margin_acl.margin_transaction_line(self.env)
        lines = Line.search(
            [
                ("transaction_id", "in", txs.ids),
                ("line_type", "=", "cost"),
                ("state", "!=", "excluded"),
                ("cost_source", "in", ("inventory", "manual")),
            ]
        )
        return sum(lines.mapped("amount_company_currency") or lines.mapped("amount_untaxed") or [0.0])

    @api.model
    def refresh_sale_costs(self, sale_order):
        """Re-read live PO/ASG into MTX estimated lines, then return compute dict."""
        txs = self._linked_transactions(sale_order)
        alloc = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        for tx in txs:
            alloc.refresh_estimated_costs_from_live_assignments(tx)
            # Auto-close normal ops when coverage is complete (no manual MTX visit).
            alloc.confirm_explicit_hub_relation(tx)
        return self.compute_for_sale_order(sale_order, refresh=False)

    @api.model
    def compute_for_sale_order(self, sale_order, refresh=False):
        empty = {
            "revenue": 0.0,
            "estimated_cost": 0.0,
            "real_cost": 0.0,
            "unallocated_cost": 0.0,
            "estimated_margin": 0.0,
            "real_margin": 0.0,
            "estimated_margin_pct": 0.0,
            "real_margin_pct": 0.0,
            "cost_source": "none",
            "cost_coverage_state": "n_a",
            "live_rows": [],
        }
        if not sale_order:
            return empty

        if refresh:
            return self.refresh_sale_costs(sale_order)

        revenue = sale_order.amount_untaxed or 0.0
        txs = self._linked_transactions(sale_order)

        live_est, live_real, live_rows = self._live_estimated_from_assignments(sale_order)
        inv_cost = self._mtx_inventory_manual_cost(txs)
        # Prefer live split; fall back to MTX stored real if live has none
        mtx_real = self._mtx_real_cost(txs)
        real_cost = (
            live_real
            if float_compare(live_real, 0.0, precision_digits=2) > 0
            else mtx_real
        )
        estimated_cost = (live_est or 0.0) + (inv_cost or 0.0)
        unallocated_cost = 0.0

        has_real = float_compare(real_cost, 0.0, precision_digits=2) > 0
        has_est = float_compare(estimated_cost, 0.0, precision_digits=2) > 0

        if has_real and has_est:
            cost_source = "mixed_bill_po"
            display_cost = real_cost + estimated_cost
        elif has_real:
            cost_source = "vendor_bill"
            display_cost = real_cost
        elif has_est:
            cost_source = "live_po_assignment" if live_est else "inventory_manual"
            if live_est and inv_cost:
                cost_source = "mixed_po_inventory"
            display_cost = estimated_cost
        else:
            estimated_cost = 0.0
            if txs:
                txs.invalidate_recordset(["cost_estimated_amount"])
                estimated_cost = sum(txs.mapped("cost_estimated_amount") or [0.0])
            if float_compare(estimated_cost + real_cost, 0.0, precision_digits=2) <= 0:
                estimated_cost, real_cost, unallocated_cost = self._legacy_costs(sale_order)
                cost_source = "legacy" if (estimated_cost or real_cost) else "none"
            else:
                cost_source = "mtx_stored"
            display_cost = (
                real_cost
                if float_compare(real_cost, 0.0, precision_digits=2) > 0
                else estimated_cost
            )
            has_real = float_compare(real_cost, 0.0, precision_digits=2) > 0
            has_est = float_compare(estimated_cost, 0.0, precision_digits=2) > 0

        coverage = "n_a"
        if txs:
            coverages = txs.mapped("cost_coverage_state")
            if coverages:
                if all(c == "complete" for c in coverages):
                    coverage = "complete"
                elif any(c in ("partial", "complete") for c in coverages):
                    coverage = "partial"
                elif any(c == "none" for c in coverages):
                    coverage = "none"

        estimated_margin = revenue - estimated_cost
        real_margin = (
            revenue - real_cost
            if float_compare(real_cost, 0.0, precision_digits=2) > 0
            else 0.0
        )
        return {
            "revenue": revenue,
            "estimated_cost": estimated_cost,
            "real_cost": real_cost,
            "unallocated_cost": unallocated_cost,
            "estimated_margin": estimated_margin,
            "real_margin": real_margin,
            "estimated_margin_pct": (estimated_margin / revenue * 100.0) if revenue else 0.0,
            "real_margin_pct": (real_margin / revenue * 100.0)
            if revenue and float_compare(real_cost, 0.0, precision_digits=2) > 0
            else 0.0,
            "cost_source": cost_source,
            "cost_coverage_state": coverage,
            "display_cost": display_cost,
            "display_margin": revenue - display_cost,
            "display_margin_pct": ((revenue - display_cost) / revenue * 100.0)
            if revenue
            else 0.0,
            "live_rows": live_rows,
        }

    @api.model
    def compute_for_sale_line(self, sale_line):
        if not sale_line:
            return {
                "revenue": 0.0,
                "real_cost": 0.0,
                "real_margin": 0.0,
                "real_margin_pct": 0.0,
            }
        so = sale_line.order_id
        data = self.compute_for_sale_order(so)
        revenue = sale_line.price_subtotal or 0.0
        line_cost = sum(
            r["cost"]
            for r in (data.get("live_rows") or [])
            if r.get("sale_line") and r["sale_line"].id == sale_line.id
        )
        if float_compare(line_cost, 0.0, precision_digits=2) <= 0:
            allocations = margin_acl.margin_cost_allocation(self.env).search(
                [
                    ("sale_order_line_id", "=", sale_line.id),
                    ("state", "in", ("confirmed", "complete", "partial")),
                    ("exclude_from_sales_margin", "=", False),
                    ("cost_usage_type", "!=", "administrative_expense"),
                ]
            )
            line_cost = sum(allocations.mapped("allocated_amount_company_currency"))
        real_margin = revenue - line_cost
        return {
            "revenue": revenue,
            "real_cost": line_cost,
            "real_margin": real_margin,
            "real_margin_pct": (real_margin / revenue * 100.0) if revenue else 0.0,
        }

    @api.model
    def create_or_update_snapshot(self, sale_order):
        data = self.compute_for_sale_order(sale_order)
        Snapshot = margin_acl.margin_snapshot(self.env)
        snapshot = Snapshot.search(
            [("sale_id", "=", sale_order.id), ("state", "=", "draft")], limit=1
        )
        vals = {
            "sale_id": sale_order.id,
            "company_id": sale_order.company_id.id,
            "revenue_amount": data["revenue"],
            "estimated_cost_amount": data["estimated_cost"],
            "real_cost_amount": data["real_cost"],
            "unallocated_cost_amount": data.get("unallocated_cost") or 0.0,
        }
        if snapshot:
            snapshot.write(vals)
        else:
            snapshot = Snapshot.create(vals)
        return snapshot

    @api.model
    def cron_flag_margin_alerts(self, negative_margin_threshold=0.0, batch_size=500):
        Sale = self.env["sale.order"].search(
            [("state", "in", ("sale", "done"))], limit=batch_size
        )
        flagged = 0
        for sale in Sale:
            data = self.compute_for_sale_order(sale)
            margin = data.get("display_margin", data["real_margin"])
            if data["revenue"] and margin < negative_margin_threshold:
                flagged += 1
                _logger.warning(
                    "purchase_sale_margin_control: margen negativo en %s (%.2f)",
                    sale.name,
                    margin,
                )
        _logger.info(
            "purchase_sale_margin_control: alertas cron revisó %s órdenes, marcó %s",
            len(Sale),
            flagged,
        )
        return True
