# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import margin_acl
from .margin_cross_trace import active_purchase_orders, active_vendor_bills, margin_band_label

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    cost_allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation", "vendor_bill_id", string="Asignaciones de costo (compra)"
    )
    customer_cost_allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation", "customer_invoice_id", string="Asignaciones de costo (venta)"
    )
    cost_allocation_count = fields.Integer(compute="_compute_cost_allocation_count")
    margin_transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction", compute="_compute_margin_transaction_ids",
        string="Operaciones de margen",
    )
    margin_transaction_count = fields.Integer(compute="_compute_margin_transaction_ids")

    jm_related_sale_order_ids = fields.Many2many(
        "sale.order",
        compute="_compute_margin_cross_docs",
        string="Ventas relacionadas (margen)",
    )
    jm_related_purchase_order_ids = fields.Many2many(
        "purchase.order",
        compute="_compute_margin_cross_docs",
        string="OC relacionadas",
    )
    jm_related_purchase_order_count = fields.Integer(compute="_compute_margin_cross_docs")
    jm_related_vendor_bill_ids = fields.Many2many(
        "account.move",
        compute="_compute_margin_cross_docs",
        string="Facturas proveedor",
    )
    jm_related_vendor_bill_count = fields.Integer(compute="_compute_margin_cross_docs")
    jm_related_customer_invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_margin_cross_docs",
        string="Facturas cliente",
    )
    margin_control_cost = fields.Monetary(
        string="Costo relacionado",
        compute="_compute_margin_cross_docs",
        currency_field="currency_id",
    )
    margin_control_margin = fields.Monetary(
        string="Margen",
        compute="_compute_margin_cross_docs",
        currency_field="currency_id",
    )
    margin_control_margin_pct = fields.Float(
        string="Margen %",
        compute="_compute_margin_cross_docs",
    )
    margin_control_state = fields.Char(
        string="Estado margen",
        compute="_compute_margin_cross_docs",
    )

    # 19.0.3.0.0: Auxiliar de Cuentas por Pagar (solo facturas de proveedor)
    payable_auxiliary_id = fields.Many2one(
        "purchase.sale.payable.auxiliary", string="Auxiliar CxP",
        compute="_compute_payable_auxiliary", store=False,
    )
    has_payable_auxiliary = fields.Boolean(compute="_compute_payable_auxiliary")
    related_sale_count = fields.Integer(
        string="Ventas relacionadas",
        compute="_compute_payable_auxiliary",
    )
    margin_operational_state = fields.Selection(
        [
            ("pending_relation", "Pendiente de relación"),
            ("partial_relation", "Relación parcial"),
            ("full_relation", "Relación completa"),
            ("invoiced_to_customer", "Facturado a cliente"),
            ("pending_customer_collection", "Pendiente de cobro a cliente"),
            ("pending_vendor_payment", "Pendiente de pago a proveedor"),
            ("partial_paid", "Pagada parcialmente"),
            ("paid", "Pagada"),
            ("closed", "Cerrada"),
        ],
        string="Estado operativo CxP", compute="_compute_payable_auxiliary",
    )

    @api.depends("cost_allocation_ids", "customer_cost_allocation_ids")
    def _compute_cost_allocation_count(self):
        Alloc = margin_acl.margin_cost_allocation(self.env)
        for rec in self:
            # O2M may be ACL-blocked for users without Margin; count via sudo.
            vendor_n = Alloc.search_count([("vendor_bill_id", "=", rec.id)])
            customer_n = Alloc.search_count([("customer_invoice_id", "=", rec.id)])
            rec.cost_allocation_count = vendor_n + customer_n

    def _compute_payable_auxiliary(self):
        Auxiliary = margin_acl.margin_payable_auxiliary(self.env)
        Transaction = margin_acl.margin_transaction(self.env)
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            if rec.move_type not in ("in_invoice", "in_refund"):
                rec.payable_auxiliary_id = False
                rec.has_payable_auxiliary = False
                rec.related_sale_count = 0
                rec.margin_operational_state = False
                continue
            aux = Auxiliary.search([("vendor_bill_id", "=", rec.id)], limit=1)
            # Cache M2O without comodel ACL (Margin models stay hidden).
            margin_acl.cache_set_m2o(
                rec, "payable_auxiliary_id", aux.id if (can_see and aux) else False
            )
            rec.has_payable_auxiliary = bool(aux)
            txs = Transaction.search(
                [("vendor_bill_ids", "in", rec.id)] + Transaction._operational_domain()
            )
            sale_ids = set(txs.mapped("sale_order_ids").ids)
            if aux:
                sale_ids.update(aux.sale_order_ids.ids)
            rec.related_sale_count = len(sale_ids)
            rec.margin_operational_state = (
                (aux.operational_state if aux else False) if can_see else False
            )

    def _compute_margin_transaction_ids(self):
        # Technical read: must not raise AccessError for Accounting-only users.
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            if rec.move_type in ("in_invoice", "in_refund"):
                transactions = Transaction.search([("vendor_bill_ids", "in", rec.id)] + op_domain)
            elif rec.move_type in ("out_invoice", "out_refund"):
                transactions = Transaction.search([("customer_invoice_ids", "in", rec.id)] + op_domain)
            else:
                transactions = Transaction.browse()
            # M2M assignment checks comodel ACL — use cache for isolation.
            margin_acl.cache_set_m2m(
                rec, "margin_transaction_ids", transactions.ids if can_see else ()
            )
            rec.margin_transaction_count = len(transactions) if can_see else 0

    def _compute_margin_cross_docs(self):
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            if rec.move_type in ("in_invoice", "in_refund"):
                txs = Transaction.search([("vendor_bill_ids", "in", rec.id)] + op_domain)
            elif rec.move_type in ("out_invoice", "out_refund"):
                txs = Transaction.search([("customer_invoice_ids", "in", rec.id)] + op_domain)
            else:
                txs = Transaction.browse()
            sos = txs.mapped("sale_order_ids").filtered(lambda s: s.state != "cancel")
            pos = active_purchase_orders(txs.mapped("purchase_order_ids"))
            bills = active_vendor_bills(txs.mapped("vendor_bill_ids") - rec)
            invs = (txs.mapped("customer_invoice_ids") - rec).filtered(
                lambda m: m.state != "cancel"
            )
            if can_see:
                margin_acl.cache_set_m2m_records(rec, "jm_related_sale_order_ids", sos)
                margin_acl.cache_set_m2m_records(rec, "jm_related_purchase_order_ids", pos)
                margin_acl.cache_set_m2m_records(rec, "jm_related_vendor_bill_ids", bills)
                margin_acl.cache_set_m2m_records(rec, "jm_related_customer_invoice_ids", invs)
            else:
                margin_acl.cache_set_m2m(rec, "jm_related_sale_order_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_purchase_order_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_vendor_bill_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_customer_invoice_ids", ())
            rec.jm_related_purchase_order_count = len(pos) if can_see else 0
            rec.jm_related_vendor_bill_count = len(bills) if can_see else 0
            cost = sum(txs.mapped("display_cost_amount")) if txs else 0.0
            margin = sum(txs.mapped("display_margin_amount")) if txs else 0.0
            if rec.move_type in ("out_invoice", "out_refund"):
                sale_u = rec.amount_untaxed
            else:
                sale_u = sum(txs.mapped("display_sale_amount")) if txs else 0.0
            if len(txs) == 1:
                pct = txs.display_margin_pct or 0.0
            else:
                pct = (margin / sale_u * 100.0) if sale_u else 0.0
            # txs already sudo via margin_transaction(); safe to read margin_band.
            bands = txs.mapped("margin_band") if txs else []
            band = bands[0] if bands else "pending"
            rec.margin_control_cost = cost if can_see else 0.0
            rec.margin_control_margin = margin if can_see else 0.0
            rec.margin_control_margin_pct = pct if can_see else 0.0
            rec.margin_control_state = margin_band_label(band) if can_see else False


    def action_view_margin_transactions(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Operaciones de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "list,form",
            "domain": [("id", "in", self.margin_transaction_ids.ids)],
        }
        if len(self.margin_transaction_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.margin_transaction_ids.id})
        return action

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
        context = {"default_company_id": self.company_id.id}
        if self.move_type in ("in_invoice", "in_refund"):
            context["default_vendor_bill_ids"] = [(6, 0, [self.id])]
            context["default_supplier_ids"] = [(6, 0, [self.partner_id.id])] if self.partner_id else False
        else:
            context["default_customer_invoice_ids"] = [(6, 0, [self.id])]
            context["default_customer_id"] = self.partner_id.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear/vincular operación de margen"),
            "res_model": "purchase.sale.create.transaction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_open_cost_allocations(self):
        self.ensure_one()
        domain = (
            [("vendor_bill_id", "=", self.id)]
            if self.move_type in ("in_invoice", "in_refund")
            else [("customer_invoice_id", "=", self.id)]
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignaciones de costo"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": domain,
        }

    # ------------------------------------------------------------------
    # 19.0.8.29.22 — UX hub: Gestionar compras (single entry on invoice)
    # ------------------------------------------------------------------
    def action_manage_purchases(self):
        """Single visible entry: hub wizard. Reuses existing MTX; never duplicates."""
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("Esta acción solo aplica a facturas de cliente."))
        sos = self.invoice_line_ids.mapped("sale_line_ids.order_id")
        ctx = {
            "active_id": self.id,
            "active_ids": [self.id],
            "active_model": "account.move",
            "default_customer_invoice_ids": [(6, 0, [self.id])],
            "default_customer_id": self.partner_id.commercial_partner_id.id,
            "default_company_id": self.company_id.id,
            "default_sale_order_ids": [(6, 0, sos.ids)] if sos else False,
            "default_salesperson_id": sos[:1].user_id.id if sos[:1].user_id else False,
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
        """Backend/canonical Relacionar compras (multi-vendor). Kept for internal callers."""
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("Esta acción solo aplica a facturas de cliente."))
        sos = self.invoice_line_ids.mapped("sale_line_ids.order_id")
        return {
            "type": "ir.actions.act_window",
            "name": _("Relacionar compras"),
            "res_model": "purchase.sale.create.transaction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_customer_invoice_ids": [(6, 0, [self.id])],
                "default_customer_id": self.partner_id.commercial_partner_id.id,
                "default_company_id": self.company_id.id,
                "default_sale_order_ids": [(6, 0, sos.ids)] if sos else False,
                "default_salesperson_id": sos[:1].user_id.id if sos[:1].user_id else False,
            },
        }

    def action_relate_purchases(self):
        """Legacy name → hub (visible UX). Internal multi-vendor remains action_add_purchase_orders."""
        return self.action_manage_purchases()

    def action_justech_invoice_buy_pending(self):
        """Trace invoice button → hub (method kept; view hidden when Trace present)."""
        return self.action_manage_purchases()

    def action_justech_invoice_link_existing_po(self):
        """Trace invoice button → hub (method kept; view hidden when Trace present)."""
        return self.action_manage_purchases()

    def _register_hook(self):
        """Rebind Trace invoice purchase actions after full registry merge."""
        super()._register_hook()
        from odoo.addons.justech_purchase_sale_margin_control.hooks import (
            redirect_trace_invoice_purchase_actions,
        )

        redirect_trace_invoice_purchase_actions(self.env)

    # ------------------------------------------------------------------
    # 19.0.3.0.0 — Requerimiento 2: Auxiliar de Cuentas por Pagar
    # ------------------------------------------------------------------
    def _ensure_payable_auxiliary(self):
        """Create the operational purchase.sale.payable.auxiliary control
        record for this vendor bill if it does not exist yet. Only applies
        to in_invoice/in_refund and never alters accounting fields/amounts;
        it only creates a satellite control record."""
        # Satellite Margin control — sudo on Auxiliary only, never on account.move.
        Auxiliary = margin_acl.margin_payable_auxiliary(self.env)
        Transaction = margin_acl.margin_transaction(self.env)
        created = Auxiliary
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            existing = Auxiliary.search([("vendor_bill_id", "=", move.id)], limit=1)
            if existing:
                continue
            po_line = move.invoice_line_ids.mapped("purchase_line_id")[:1]
            sale_ids = False
            if po_line:
                txs = Transaction.search(
                    [("purchase_order_ids", "in", po_line.order_id.ids)]
                    + Transaction._operational_domain()
                )
                sale_ids = [(6, 0, txs.mapped("sale_order_ids").ids)]
            created |= Auxiliary.create(
                {
                    "company_id": move.company_id.id,
                    "vendor_bill_id": move.id,
                    "sale_order_ids": sale_ids,
                }
            )
        return created

    def action_view_payable_auxiliary(self):
        self.ensure_one()
        aux = self.payable_auxiliary_id or self._ensure_payable_auxiliary()
        if not aux:
            raise UserError(_("Solo las facturas de proveedor tienen auxiliar de CxP."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Auxiliar de cuentas por pagar"),
            "res_model": "purchase.sale.payable.auxiliary",
            "view_mode": "form",
            "res_id": aux.id,
        }

    def action_relate_sales(self):
        self.ensure_one()
        if self.move_type not in ("in_invoice", "in_refund"):
            raise UserError(_("Esta acción solo aplica a facturas de proveedor."))
        aux = self.payable_auxiliary_id or self._ensure_payable_auxiliary()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relacionar ventas"),
            "res_model": "purchase.sale.relate.sale.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payable_auxiliary_id": aux.id,
                "default_vendor_bill_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_related_sales(self):
        self.ensure_one()
        # Prefer margin hub; fall back to payable auxiliary
        orders = self.jm_related_sale_order_ids
        if not orders and self.payable_auxiliary_id:
            orders = self.payable_auxiliary_id.sale_order_ids
        if not orders:
            return self.action_relate_sales()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Ventas relacionadas"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", orders.ids)],
        }
        if len(orders) == 1:
            action.update({"view_mode": "form", "res_id": orders.id})
        return action

    def action_classify_costs(self):
        """'Clasificar...' button: re-run the existing cost-classification
        suggestion service on every purchase.order.line behind this bill,
        without ever touching accounting fields."""
        for move in self:
            lines = move.invoice_line_ids.mapped("purchase_line_id").filtered(lambda l: not l.classification_is_manual)
            lines.action_suggest_classification()
        return True

    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            try:
                move._trigger_margin_trace_suggestions()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "purchase_sale_margin_control: no se pudo sugerir trazabilidad para %s",
                    move.name,
                )
            try:
                move._ensure_payable_auxiliary()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "purchase_sale_margin_control: no se pudo crear el auxiliar de CxP para %s",
                    move.name,
                )
            try:
                from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
                    LineAllocationService,
                )

                LineAllocationService(move.env).refresh_estimated_to_real_from_bill(move)
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "purchase_sale_margin_control: no se pudo actualizar costo real para %s",
                    move.name,
                )
        return res

    def _justech_margin_ncf(self):
        self.ensure_one()
        for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
            if fname in self._fields and self[fname]:
                return self[fname]
        return self.ref or ""

    @api.model
    def _justech_margin_wizard_restrict_domain(self, domain):
        from odoo.osv import expression

        ctx = self.env.context
        if not ctx.get("justech_margin_wizard"):
            return domain
        company_id = ctx.get("justech_margin_wizard_company_id")
        customer_id = ctx.get("justech_margin_wizard_customer_id")
        supplier_id = ctx.get("justech_margin_wizard_supplier_id")
        supplier_ids = ctx.get("justech_margin_wizard_supplier_ids") or []
        if isinstance(supplier_ids, int):
            supplier_ids = [supplier_ids]
        parts = [domain] if domain else []
        if company_id:
            parts.append([("company_id", "=", company_id)])
        if "justech_margin_wizard_customer_id" in ctx:
            if customer_id:
                parts.append([("partner_id", "child_of", customer_id)])
            else:
                parts.append([("id", "=", False)])
        elif supplier_ids or "justech_margin_wizard_supplier_ids" in ctx:
            if supplier_ids:
                parts.append([("partner_id", "child_of", list(supplier_ids))])
            else:
                parts.append([("id", "=", False)])
        elif "justech_margin_wizard_supplier_id" in ctx:
            if supplier_id:
                parts.append([("partner_id", "child_of", supplier_id)])
            else:
                parts.append([("id", "=", False)])
        return expression.AND(parts) if parts else domain

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        domain = self._justech_margin_wizard_restrict_domain(list(domain or []))
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        from odoo.osv import expression

        domain = self._justech_margin_wizard_restrict_domain(list(domain or []))
        if self.env.context.get("justech_margin_show_ncf") and name:
            ncf_domain = ["|", ("name", operator, name), ("ref", operator, name)]
            for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
                if fname in self._fields:
                    ncf_domain = ["|", (fname, operator, name)] + ncf_domain
            full = expression.AND([ncf_domain, domain]) if domain else ncf_domain
            moves = self.search(full, limit=limit)
            return [(m.id, m._justech_margin_display_name()) for m in moves]
        return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

    def _justech_margin_display_name(self):
        self.ensure_one()
        ncf = self._justech_margin_ncf()
        partner = self.partner_id.display_name or ""
        base = self.name or _("Borrador")
        if ncf and partner:
            return f"{base} · NCF {ncf} · {partner}"
        if ncf:
            return f"{base} · NCF {ncf}"
        if partner:
            return f"{base} · {partner}"
        return base

    def name_get(self):
        if self.env.context.get("justech_margin_show_ncf"):
            return [(m.id, m._justech_margin_display_name()) for m in self]
        return super().name_get()

    def _trigger_margin_trace_suggestions(self):
        Trace = self.env["purchase.sale.trace.engine"]
        for line in self.invoice_line_ids.filtered(lambda l: l.purchase_line_id):
            Trace.create_suggested_allocation(line)
        return True
