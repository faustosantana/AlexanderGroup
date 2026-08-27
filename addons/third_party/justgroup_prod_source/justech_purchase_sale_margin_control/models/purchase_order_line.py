# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from . import margin_acl
from .cost_link import COST_USAGE


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    cost_usage_type = fields.Selection(
        COST_USAGE,
        string="Clasificación de costo",
        default="inventory_pending",
        tracking=True,
        copy=False,
    )
    classification_is_manual = fields.Boolean(
        string="Clasificación manual", default=False, copy=False
    )
    classification_confidence = fields.Integer(
        string="Confianza clasificación %", default=0, copy=False
    )
    classification_reason = fields.Char(string="Motivo clasificación", copy=False, readonly=True)
    exclude_from_sales_margin = fields.Boolean(string="Excluir del margen de venta", copy=False)

    cost_link_ids = fields.One2many(
        "purchase.sale.cost.link", "purchase_line_id", string="Enlaces de costo"
    )
    cost_link_count = fields.Integer(compute="_compute_cost_link_count")

    @api.depends("cost_link_ids")
    def _compute_cost_link_count(self):
        Link = margin_acl.margin_cost_link(self.env)
        for rec in self:
            rec.cost_link_count = Link.search_count([("purchase_line_id", "=", rec.id)])

    def write(self, vals):
        if (
            "cost_usage_type" in vals
            and "classification_is_manual" not in vals
            and not self.env.context.get("skip_manual_flag")
        ):
            vals = dict(vals, classification_is_manual=True)
        res = super().write(vals)
        # Live cost invalidation when commercial amounts change.
        watch = {
            "price_unit",
            "product_qty",
            "product_uom_qty",
            "discount",
            "taxes_id",
            "sale_line_id",
        }
        if not self.env.context.get("skip_margin_live_cost_refresh") and watch.intersection(
            vals
        ):
            self._margin_refresh_related_live_costs()
        return res

    def _margin_refresh_related_live_costs(self):
        """When POL price/qty changes, refresh MTX estimated costs for linked sales."""
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        Tx = margin_acl.margin_transaction(self.env)
        alloc = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        seen = self.env["purchase.sale.margin.transaction"]
        for pol in self:
            txs = Tx.search(
                [
                    "|",
                    ("line_ids.purchase_order_line_id", "=", pol.id),
                    ("purchase_order_ids", "in", pol.order_id.ids),
                ]
            )
            # Also via ASG / sale_line
            if pol.sale_line_id:
                txs |= Tx.search([("sale_order_ids", "in", pol.sale_line_id.order_id.ids)])
            if "justech.purchase.sale.qty.assignment" in self.env:
                Assign = self.env["justech.purchase.sale.qty.assignment"].sudo()
                sols = Assign.search(
                    [("purchase_line_id", "=", pol.id), ("state", "=", "active")]
                ).mapped("sale_line_id.order_id")
                if sols:
                    txs |= Tx.search([("sale_order_ids", "in", sols.ids)])
            for tx in txs - seen:
                alloc.refresh_estimated_costs_from_live_assignments(tx)
                alloc.confirm_explicit_hub_relation(tx)
                seen |= tx
                # Invalidate linked SO panels
                sos = tx.sale_order_ids
                if sos:
                    sos.invalidate_recordset(
                        [
                            "real_cost_amount",
                            "estimated_cost_amount",
                            "margin_control_cost",
                            "margin_control_margin",
                            "margin_control_margin_pct",
                            "margin_control_state",
                        ]
                    )

    def action_suggest_classification(self):
        Service = self.env["purchase.sale.classification.service"]
        for rec in self:
            usage_type, confidence, reason = Service.suggest_cost_usage_type(rec)
            if rec.classification_is_manual:
                continue
            rec.with_context(skip_manual_flag=True).write(
                {
                    "cost_usage_type": usage_type,
                    "classification_confidence": confidence,
                    "classification_reason": reason,
                }
            )
        return True

    def action_create_cost_link(self):
        Trace = self.env["purchase.sale.trace.engine"]
        links = self.env["purchase.sale.cost.link"]
        for rec in self:
            links |= Trace.get_or_create_link_for_purchase_line(rec)
        if not links:
            return True
        return {
            "type": "ir.actions.act_window",
            "name": _("Enlaces de costo"),
            "res_model": "purchase.sale.cost.link",
            "view_mode": "list,form",
            "domain": [("id", "in", links.ids)],
        }

    def action_open_cost_links(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enlaces de costo"),
            "res_model": "purchase.sale.cost.link",
            "view_mode": "list,form",
            "domain": [("purchase_line_id", "=", self.id)],
            "context": {"default_purchase_line_id": self.id, "default_purchase_id": self.order_id.id},
        }
