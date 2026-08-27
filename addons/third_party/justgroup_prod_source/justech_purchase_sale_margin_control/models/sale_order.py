# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from . import margin_acl
from .margin_cross_trace import (
    active_purchase_orders,
    active_vendor_bills,
    cost_origin_label,
    join_record_names,
    margin_band_label,
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def create(self, vals_list):
        """Prefer current internal user as salesperson on manual create.

        Odoo copies partner.user_id into sale.order.user_id. That silently
        assigns a historical contact salesperson (e.g. recepcion@) even when
        Fausto creates the quotation. Keep explicit user_id; otherwise use
        env.user for internal Sales users.
        """
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if (
                not self.env.context.get("justech_keep_partner_salesperson")
                and not self.env.context.get("website_id")
                and not self.env.user.share
            ):
                partner = (
                    self.env["res.partner"].browse(vals["partner_id"])
                    if vals.get("partner_id")
                    else self.env["res.partner"]
                )
                partner_user_id = partner.user_id.id if partner and partner.user_id else False
                explicit = vals.get("user_id")
                if not explicit or explicit == partner_user_id:
                    vals["user_id"] = self.env.user.id
            prepared.append(vals)
        return super().create(prepared)

    cost_link_ids = fields.One2many("purchase.sale.cost.link", "sale_id", string="Enlaces de costo")
    cost_link_count = fields.Integer(compute="_compute_cost_link_count")
    cost_allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation", "sale_order_id", string="Asignaciones de costo"
    )
    cost_allocation_count = fields.Integer(compute="_compute_cost_link_count")
    margin_snapshot_ids = fields.One2many(
        "purchase.sale.margin.snapshot", "sale_id", string="Fotos de margen"
    )
    margin_transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction",
        compute="_compute_margin_transaction_ids",
        string="Operaciones de margen",
    )
    margin_transaction_count = fields.Integer(compute="_compute_margin_transaction_ids")

    jm_related_purchase_order_ids = fields.Many2many(
        "purchase.order",
        compute="_compute_margin_related_docs",
        string="OC relacionadas",
    )
    jm_related_purchase_order_count = fields.Integer(compute="_compute_margin_related_docs")
    jm_related_vendor_bill_ids = fields.Many2many(
        "account.move",
        compute="_compute_margin_related_docs",
        string="Facturas proveedor",
    )
    jm_related_vendor_bill_count = fields.Integer(compute="_compute_margin_related_docs")
    jm_related_customer_invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_margin_related_docs",
        string="Facturas cliente",
    )
    jm_related_customer_invoice_count = fields.Integer(compute="_compute_margin_related_docs")
    margin_control_sale_untaxed = fields.Monetary(
        string="Venta sin ITBIS",
        compute="_compute_margin_control_panel",
        currency_field="currency_id",
    )
    margin_control_cost = fields.Monetary(
        string="Costo relacionado",
        compute="_compute_margin_control_panel",
        currency_field="currency_id",
    )
    margin_control_margin = fields.Monetary(
        string="Margen",
        compute="_compute_margin_control_panel",
        currency_field="currency_id",
    )
    margin_control_margin_pct = fields.Float(
        string="Margen %",
        compute="_compute_margin_control_panel",
    )
    margin_control_state = fields.Char(
        string="Estado",
        compute="_compute_margin_control_panel",
    )
    margin_control_po_names = fields.Char(
        string="OC relacionadas",
        compute="_compute_margin_control_panel",
    )
    margin_control_bill_names = fields.Char(
        string="Facturas proveedor",
        compute="_compute_margin_control_panel",
    )
    margin_control_cost_origin = fields.Char(
        string="Origen del costo",
        compute="_compute_margin_control_panel",
    )
    margin_control_primary_po_id = fields.Many2one(
        "purchase.order",
        string="Orden de compra",
        compute="_compute_margin_control_panel",
    )
    margin_control_primary_bill_id = fields.Many2one(
        "account.move",
        string="Factura proveedor",
        compute="_compute_margin_control_panel",
    )

    estimated_margin = fields.Monetary(
        string="Margen estimado", compute="_compute_margin_fields", currency_field="currency_id"
    )
    estimated_margin_pct = fields.Float(string="Margen estimado %", compute="_compute_margin_fields")
    real_margin = fields.Monetary(
        string="Margen real", compute="_compute_margin_fields", currency_field="currency_id"
    )
    real_margin_pct = fields.Float(string="Margen real %", compute="_compute_margin_fields")
    real_cost_amount = fields.Monetary(
        string="Costo real", compute="_compute_margin_fields", currency_field="currency_id"
    )
    estimated_cost_amount = fields.Monetary(
        string="Costo estimado", compute="_compute_margin_fields", currency_field="currency_id"
    )

    @api.depends("cost_link_ids", "cost_allocation_ids")
    def _compute_cost_link_count(self):
        Link = margin_acl.margin_cost_link(self.env)
        Alloc = margin_acl.margin_cost_allocation(self.env)
        for rec in self:
            rec.cost_link_count = Link.search_count([("sale_id", "=", rec.id)])
            rec.cost_allocation_count = Alloc.search_count([("sale_order_id", "=", rec.id)])

    def _compute_margin_fields(self):
        """Canonical costs = linked MTX (via MarginService)."""
        MarginService = self.env["purchase.sale.margin.service"]
        for rec in self:
            data = MarginService.compute_for_sale_order(rec)
            rec.estimated_margin = data["estimated_margin"]
            rec.estimated_margin_pct = data["estimated_margin_pct"]
            rec.real_margin = data["real_margin"]
            rec.real_margin_pct = data["real_margin_pct"]
            rec.real_cost_amount = data["real_cost"]
            rec.estimated_cost_amount = data["estimated_cost"]

    def _compute_margin_transaction_ids(self):
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            transactions = Transaction.search([("sale_order_ids", "in", rec.id)] + op_domain)
            margin_acl.cache_set_m2m(
                rec, "margin_transaction_ids", transactions.ids if can_see else ()
            )
            rec.margin_transaction_count = len(transactions) if can_see else 0

    def _compute_margin_related_docs(self):
        """Siempre desde el hub MTX (sin cache stale de M2M).

        Cancelled POs/bills remain on MTX for audit but are excluded from UX
        related docs, counters and smart buttons.
        """
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            txs = Transaction.search([("sale_order_ids", "in", rec.id)] + op_domain)
            pos = active_purchase_orders(txs.mapped("purchase_order_ids"))
            bills = active_vendor_bills(txs.mapped("vendor_bill_ids"))
            invs = txs.mapped("customer_invoice_ids").filtered(lambda m: m.state != "cancel")
            if can_see:
                margin_acl.cache_set_m2m_records(rec, "jm_related_purchase_order_ids", pos)
                margin_acl.cache_set_m2m_records(rec, "jm_related_vendor_bill_ids", bills)
                margin_acl.cache_set_m2m_records(rec, "jm_related_customer_invoice_ids", invs)
            else:
                margin_acl.cache_set_m2m(rec, "jm_related_purchase_order_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_vendor_bill_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_customer_invoice_ids", ())
            rec.jm_related_purchase_order_count = len(pos) if can_see else 0
            rec.jm_related_vendor_bill_count = len(bills) if can_see else 0
            rec.jm_related_customer_invoice_count = len(invs) if can_see else 0

    @api.depends(
        "amount_untaxed",
        "real_cost_amount",
        "estimated_cost_amount",
        "real_margin",
        "estimated_margin",
        "real_margin_pct",
        "estimated_margin_pct",
        "jm_related_purchase_order_ids",
        "jm_related_vendor_bill_ids",
        "margin_transaction_ids",
        # NEVER depend on margin_transaction_ids.margin_band — that field is
        # groups-restricted (Márgenes ver) and breaks Gestionar compras / SO
        # web_read for commercial users.
    )
    def _compute_margin_control_panel(self):
        """Panel mirrors MTX canonical costs (same as invoice panel)."""
        Tx = margin_acl.margin_transaction(self.env)
        MarginService = self.env["purchase.sale.margin.service"]
        for rec in self:
            data = MarginService.compute_for_sale_order(rec)
            cost = data.get("display_cost") or 0.0
            margin = data.get("display_margin")
            if margin is None:
                margin = (rec.amount_untaxed or 0.0) - cost
            pct = data.get("display_margin_pct")
            if pct is None:
                pct = (margin / rec.amount_untaxed * 100.0) if rec.amount_untaxed else 0.0

            tx_ids = rec.margin_transaction_ids.ids
            if not tx_ids:
                tx_ids = Tx.search([("sale_order_ids", "in", rec.id)]).ids
            txs = Tx.browse(tx_ids) if tx_ids else Tx.browse()

            coverage = data.get("cost_coverage_state") or "n_a"
            # Operational cost status first; financial exception if margin negative.
            if coverage == "complete" and (pct or 0) < 0:
                state_label = _("⚠ EXCEPCIÓN — Margen negativo")
            elif coverage == "complete":
                state_label = _("🟢 Costos confirmados")
            elif coverage == "partial":
                state_label = _("🟡 Costos pendientes")
            elif coverage == "none" or not cost:
                state_label = _("🔴 Costos pendientes")
            else:
                bands = txs.mapped("margin_band") if txs else []
                state_label = margin_band_label(bands[0] if bands else "pending")

            # Origin: estimated OC vs real bill (supports partial mix; zero bills ignored)
            has_real = float(data.get("real_cost") or 0.0) > 0
            has_est = float(data.get("estimated_cost") or 0.0) > 0
            if has_real and has_est:
                origin = _("Factura proveedor (real) + Orden de compra (estimado)")
            elif has_real:
                origin = _("Factura proveedor (real)")
            elif has_est:
                origin = _("Orden de compra (estimado)")
            else:
                origin = cost_origin_label(txs)

            rec.margin_control_sale_untaxed = rec.amount_untaxed
            rec.margin_control_cost = cost
            rec.margin_control_margin = margin
            rec.margin_control_margin_pct = pct
            rec.margin_control_state = state_label
            pos_active = active_purchase_orders(rec.jm_related_purchase_order_ids)
            bills_active = active_vendor_bills(rec.jm_related_vendor_bill_ids)
            rec.margin_control_po_names = join_record_names(pos_active)
            rec.margin_control_bill_names = join_record_names(bills_active)
            rec.margin_control_cost_origin = origin
            rec.margin_control_primary_po_id = pos_active[:1]
            rec.margin_control_primary_bill_id = bills_active[:1]

    def action_view_margin_transactions(self):
        """Open business cost breakdown (not technical MTX form)."""
        self.ensure_one()
        return self.env["purchase.sale.cost.breakdown.wizard"].open_for_sale_order(self)

    def action_view_margin_transactions_technical(self):
        """Admin/audit: open raw margin.transaction records."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Operaciones de margen (técnico)"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "list,form",
            "domain": [("id", "in", self.margin_transaction_ids.ids)],
        }
        if len(self.margin_transaction_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.margin_transaction_ids.id})
        return action

    def _get_purchase_orders(self):
        """Exclude cancelled POs from sale_purchase 'Compras' smart button."""
        orders = super()._get_purchase_orders()
        return orders.filtered(lambda p: p.state != "cancel")

    def action_view_related_purchase_orders(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Órdenes de compra"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.jm_related_purchase_order_ids.ids)],
        }
        if len(self.jm_related_purchase_order_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.jm_related_purchase_order_ids.id})
        return action

    def action_view_related_vendor_bills(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Facturas proveedor"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.jm_related_vendor_bill_ids.ids)],
        }
        if len(self.jm_related_vendor_bill_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.jm_related_vendor_bill_ids.id})
        return action

    def action_create_or_link_margin_transaction(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear/vincular operación de margen"),
            "res_model": "purchase.sale.create.transaction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_ids": [(6, 0, [self.id])],
                "default_customer_id": self.partner_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_manage_purchases(self):
        """Single visible entry: Gestionar compras hub (reuse MTX).

        Pre-create the transient so ARTÍCULOS are populated before the dialog
        renders. OWL forms opened without res_id only run default_get — which
        does not build line_ids (those are created in create/_refresh_coverage).
        """
        self.ensure_one()
        ctx = {
            "active_id": self.id,
            "active_ids": [self.id],
            "active_model": "sale.order",
            "default_sale_order_ids": [(6, 0, [self.id])],
            "default_customer_id": self.partner_id.commercial_partner_id.id,
            "default_company_id": self.company_id.id,
            "default_salesperson_id": self.user_id.id if self.user_id else False,
        }
        wiz = (
            self.env["purchase.sale.manage.purchases.wizard"]
            .with_context(**ctx)
            .create({})
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar compras"),
            "res_model": "purchase.sale.manage.purchases.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": ctx,
        }

    def action_add_purchase_orders(self):
        """Canonical: open purchase-first Relacionar compras wizard (no full-PO dump)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relacionar compras"),
            "res_model": "purchase.sale.create.transaction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_sale_order_ids": [(6, 0, [self.id])],
                "default_customer_id": self.partner_id.commercial_partner_id.id,
                "default_company_id": self.company_id.id,
                "default_salesperson_id": self.user_id.id if self.user_id else False,
            },
        }

    def action_relate_purchases(self):
        """Visible UX → hub; keep action_add_purchase_orders for multi-vendor engine."""
        return self.action_manage_purchases()

    def action_justech_link_existing_po(self):
        """Trace legacy entry → Gestionar compras (button hidden; method kept)."""
        return self.action_manage_purchases()

    def _register_hook(self):
        super()._register_hook()
        from odoo.addons.justech_purchase_sale_margin_control.hooks import (
            redirect_trace_sale_purchase_actions,
        )

        redirect_trace_sale_purchase_actions(self.env)

    def action_open_cost_links(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enlaces de costo"),
            "res_model": "purchase.sale.cost.link",
            "view_mode": "list,form",
            "domain": [("sale_id", "=", self.id)],
            "context": {"default_sale_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_open_cost_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignaciones de costo"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": [("sale_order_id", "=", self.id)],
            "context": {"default_sale_order_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_compute_margin_snapshot(self):
        """Live refresh: re-read current PO/bill → update MTX → SO panel → snapshot."""
        MarginService = self.env["purchase.sale.margin.service"]
        messages = []
        for rec in self:
            data = MarginService.refresh_sale_costs(rec)
            MarginService.create_or_update_snapshot(rec)
            rec.invalidate_recordset(
                [
                    "real_cost_amount",
                    "estimated_cost_amount",
                    "real_margin",
                    "estimated_margin",
                    "real_margin_pct",
                    "estimated_margin_pct",
                    "margin_control_cost",
                    "margin_control_margin",
                    "margin_control_margin_pct",
                    "margin_control_state",
                    "margin_control_cost_origin",
                ]
            )
            messages.append(
                _(
                    "%(so)s — Venta %(sale).2f · Costo %(cost).2f · Margen %(margin).2f (%(pct).2f%%) [%(src)s]"
                )
                % {
                    "so": rec.name,
                    "sale": data.get("revenue") or 0.0,
                    "cost": data.get("display_cost") or 0.0,
                    "margin": data.get("display_margin") or 0.0,
                    "pct": data.get("display_margin_pct") or 0.0,
                    "src": data.get("cost_source") or "",
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Margen recalculado (vivo)"),
                "message": "\n".join(messages),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        domain = self._justech_margin_wizard_restrict_domain(list(domain or []))
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = self._justech_margin_wizard_restrict_domain(list(domain or []))
        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

    @api.model
    def _justech_margin_wizard_restrict_domain(self, domain):
        """Enforce company+customer filter for create/link margin wizard selectors."""
        from odoo.osv import expression

        ctx = self.env.context
        if not ctx.get("justech_margin_wizard"):
            return domain
        company_id = ctx.get("justech_margin_wizard_company_id")
        customer_id = ctx.get("justech_margin_wizard_customer_id")
        parts = [domain] if domain else []
        if company_id:
            parts.append([("company_id", "=", company_id)])
        if customer_id:
            parts.append([("partner_id", "child_of", customer_id)])
        elif "justech_margin_wizard_customer_id" in ctx:
            parts.append([("id", "=", False)])
        return expression.AND(parts) if parts else domain
