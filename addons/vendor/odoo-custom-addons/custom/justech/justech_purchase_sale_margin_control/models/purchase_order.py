# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

from . import margin_acl


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cost_link_ids = fields.One2many(
        "purchase.sale.cost.link", "purchase_id", string="Enlaces de costo"
    )
    cost_link_count = fields.Integer(compute="_compute_cost_link_count")
    margin_review_needed = fields.Boolean(
        string="Requiere revisión de margen", compute="_compute_margin_review_needed"
    )
    margin_transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction",
        compute="_compute_margin_transaction_ids",
        string="Operaciones de margen",
    )
    margin_transaction_count = fields.Integer(compute="_compute_margin_transaction_ids")

    jm_related_sale_order_ids = fields.Many2many(
        "sale.order",
        compute="_compute_margin_related_docs",
        string="Ventas relacionadas",
    )
    jm_related_sale_order_count = fields.Integer(compute="_compute_margin_related_docs")
    jm_related_customer_invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_margin_related_docs",
        string="Facturas cliente",
    )
    jm_related_customer_invoice_count = fields.Integer(compute="_compute_margin_related_docs")
    margin_assigned_cost = fields.Monetary(
        string="Costo asignado",
        compute="_compute_margin_related_docs",
        currency_field="currency_id",
    )
    margin_usage_labels = fields.Char(
        string="Clasificación costo",
        compute="_compute_margin_related_docs",
    )
    margin_link_sale_id = fields.Many2one(
        "sale.order",
        string="Venta relacionada",
        compute="_compute_margin_link_summary",
    )
    margin_link_coverage_qty = fields.Float(
        string="Cobertura (uds)",
        compute="_compute_margin_link_summary",
        digits="Product Unit of Measure",
    )
    margin_link_summary_html = fields.Html(
        string="Resumen vinculación",
        compute="_compute_margin_link_summary",
        sanitize=False,
    )

    @api.depends("cost_link_ids")
    def _compute_cost_link_count(self):
        Link = margin_acl.margin_cost_link(self.env)
        for rec in self:
            rec.cost_link_count = Link.search_count([("purchase_id", "=", rec.id)])

    def _compute_margin_transaction_ids(self):
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            transactions = Transaction.search([("purchase_order_ids", "in", rec.id)] + op_domain)
            margin_acl.cache_set_m2m(
                rec, "margin_transaction_ids", transactions.ids if can_see else ()
            )
            rec.margin_transaction_count = len(transactions) if can_see else 0

    def _compute_margin_related_docs(self):
        Transaction = margin_acl.margin_transaction(self.env)
        op_domain = Transaction._operational_domain()
        usage_map = dict(self.env["purchase.order.line"]._fields["cost_usage_type"].selection)
        can_see = margin_acl.user_has_margin_access(self.env)
        for rec in self:
            txs = Transaction.search([("purchase_order_ids", "in", rec.id)] + op_domain)
            sos = txs.mapped("sale_order_ids")
            invs = txs.mapped("customer_invoice_ids")
            if can_see:
                margin_acl.cache_set_m2m_records(rec, "jm_related_sale_order_ids", sos)
                margin_acl.cache_set_m2m_records(rec, "jm_related_customer_invoice_ids", invs)
            else:
                margin_acl.cache_set_m2m(rec, "jm_related_sale_order_ids", ())
                margin_acl.cache_set_m2m(rec, "jm_related_customer_invoice_ids", ())
            rec.jm_related_sale_order_count = len(sos) if can_see else 0
            rec.jm_related_customer_invoice_count = len(invs) if can_see else 0
            rec.margin_assigned_cost = rec.amount_untaxed
            usages = set(
                usage_map.get(u, u)
                for u in rec.order_line.mapped("cost_usage_type")
                if u
            )
            rec.margin_usage_labels = ", ".join(sorted(str(x) for x in usages)) if usages else "—"

    def _active_linked_sale_orders(self):
        """Active commercial SO links only (not MTX/origin historical leftovers)."""
        self.ensure_one()
        sos = self.order_line.filtered(
            lambda l: not l.display_type and l.sale_line_id
        ).mapped("sale_line_id.order_id")
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            asgs = Assign.search(
                [
                    ("purchase_line_id", "in", self.order_line.ids),
                    ("state", "=", "active"),
                ]
            )
            sos |= asgs.mapped("sale_line_id.order_id")
        return sos

    def _compute_margin_link_summary(self):
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
            _is_product_line,
        )

        svc = LineAllocationService(self.env)
        for rec in self:
            # UX "venta vinculada" = active coverage only. MTX M2M may retain
            # historical SO after Desvincular / cancel and must not drive buttons.
            sale = rec._active_linked_sale_orders()[:1]
            rec.margin_link_sale_id = sale.id if sale else False
            pols = rec.order_line.filtered(_is_product_line)
            covered = 0.0
            if sale and pols:
                for pol in pols:
                    if pol.sale_line_id and pol.sale_line_id.order_id == sale:
                        covered += pol.product_qty or 0.0
                    else:
                        covered += max(
                            (pol.product_qty or 0.0) - svc.pol_qty_available(pol),
                            0.0,
                        )
            rec.margin_link_coverage_qty = covered
            if sale:
                rec.margin_link_summary_html = _(
                    "<p><b>Venta relacionada:</b> %(sale)s<br/>"
                    "<b>Costo asignado:</b> %(cost)s<br/>"
                    "<b>Cobertura:</b> %(qty).0f unidades</p>"
                ) % {
                    "sale": sale.name,
                    "cost": rec.currency_id.format(rec.amount_untaxed or 0.0),
                    "qty": covered,
                }
            else:
                rec.margin_link_summary_html = False

    def _justech_guess_link_customer(self):
        """Best-effort customer for PO link wizard (POL sale_line or MTX)."""
        self.ensure_one()
        partners = self.order_line.filtered(
            lambda l: l.sale_line_id and not l.display_type
        ).mapped("sale_line_id.order_id.partner_id.commercial_partner_id")
        if len(partners) == 1:
            return partners
        sale = self.jm_related_sale_order_ids[:1]
        if sale:
            return sale.partner_id.commercial_partner_id
        return self.env["res.partner"]

    def _justech_guess_link_sale_order(self):
        """Best-effort SO for PO link wizard (active links only)."""
        self.ensure_one()
        orders = self._active_linked_sale_orders()
        if orders:
            return orders[:1]
        return self.env["sale.order"]

    def action_link_to_sale(self):
        """Primary UX: vincular / gestionar vinculación con venta."""
        self.ensure_one()
        sale = self.margin_link_sale_id or self._justech_guess_link_sale_order()
        name = (
            _("Gestionar vinculación — %s") % sale.name
            if sale
            else _("Vincular a venta")
        )
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "purchase.sale.link.sale.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
                "default_company_id": self.company_id.id,
                "default_sale_order_id": sale.id if sale else False,
                "default_customer_id": (
                    sale.partner_id.commercial_partner_id.id
                    if sale
                    else (self._justech_guess_link_customer().id or False)
                ),
            },
        }

    def action_unlink_from_sale(self):
        """Desvincular cobertura activa PO↔SO (no borra documentos)."""
        self.ensure_one()
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        svc = LineAllocationService(self.env)
        Assign = (
            self.env["justech.purchase.sale.qty.assignment"]
            if "justech.purchase.sale.qty.assignment" in self.env
            else None
        )
        pols = self.order_line.filtered(lambda l: not l.display_type)
        sos = pols.mapped("sale_line_id.order_id")
        if Assign:
            asgs = Assign.search(
                [("purchase_line_id", "in", pols.ids), ("state", "=", "active")]
            )
            if asgs:
                asgs.write({"state": "cancelled"})
                sos |= asgs.mapped("sale_line_id.order_id")
        for pol in pols.filtered("sale_line_id"):
            pol.with_context(skip_line_sync=True).write({"sale_line_id": False})
        Link = self.env["purchase.sale.cost.link"].sudo()
        links = Link.search(
            [
                ("purchase_id", "=", self.id),
                ("state", "not in", ("cancelled", "excluded")),
            ]
        )
        if links and "state" in Link._fields:
            links.write({"state": "cancelled"})
        txs = self.margin_transaction_ids | self.env["purchase.sale.margin.transaction"].search(
            [("purchase_order_ids", "in", self.id)]
        )
        for tx in txs:
            # Exclude cost lines for this PO then refresh live.
            clines = tx.line_ids.filtered(
                lambda l: l.line_type == "cost"
                and l.purchase_order_id == self
                and l.state != "excluded"
            )
            if clines:
                clines.with_context(skip_line_sync=True).write({"state": "excluded"})
            svc.refresh_estimated_costs_from_live_assignments(tx)
        for so in sos:
            so.invalidate_recordset()
        self.invalidate_recordset()
        return True

    def action_view_margin_transactions(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Ventas / Márgenes"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "list,form",
            "domain": [("id", "in", self.margin_transaction_ids.ids)],
        }
        if len(self.margin_transaction_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.margin_transaction_ids.id})
        return action

    def action_view_related_sale_orders(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Ventas relacionadas"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.jm_related_sale_order_ids.ids)],
        }
        if len(self.jm_related_sale_order_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.jm_related_sale_order_ids.id})
        return action

    def action_create_or_link_margin_transaction(self):
        """Compat / admin: delega al wizard simple desde PO."""
        return self.action_link_to_sale()

    @api.depends("cost_link_ids.state", "cost_link_ids.confidence")
    def _compute_margin_review_needed(self):
        for rec in self:
            rec.margin_review_needed = bool(
                rec.cost_link_ids.filtered(lambda l: l.state == "draft" and l.confidence < 70)
            )

    def action_open_cost_links(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enlaces de costo"),
            "res_model": "purchase.sale.cost.link",
            "view_mode": "list,form",
            "domain": [("purchase_id", "=", self.id)],
            "context": {"default_purchase_id": self.id, "default_company_id": self.company_id.id},
        }

    def action_suggest_classification(self):
        for rec in self:
            rec.order_line.filtered(lambda l: not l.display_type).action_suggest_classification()
        return True

    def action_trace_sale_orders(self):
        Trace = self.env["purchase.sale.trace.engine"]
        for rec in self:
            for line in rec.order_line.filtered(lambda l: not l.display_type):
                Trace.get_or_create_link_for_purchase_line(line)
        return True

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
        from odoo.osv import expression

        ctx = self.env.context
        if not ctx.get("justech_margin_wizard"):
            return domain
        company_id = ctx.get("justech_margin_wizard_company_id")
        supplier_id = ctx.get("justech_margin_wizard_supplier_id")
        supplier_ids = ctx.get("justech_margin_wizard_supplier_ids") or []
        if isinstance(supplier_ids, int):
            supplier_ids = [supplier_ids]
        parts = [domain] if domain else []
        if company_id:
            parts.append([("company_id", "=", company_id)])
        if supplier_ids:
            parts.append([("partner_id", "child_of", list(supplier_ids))])
        elif supplier_id:
            parts.append([("partner_id", "child_of", supplier_id)])
        elif "justech_margin_wizard_supplier_id" in ctx or "justech_margin_wizard_supplier_ids" in ctx:
            parts.append([("id", "=", False)])
        return expression.AND(parts) if parts else domain

    def _margin_exclude_cost_lines_on_cancel(self):
        """When a PO is cancelled: drop active coverage and refresh MTX.

        - Exclude MTX estimated/accounting cost lines for this PO
        - Clear POL.sale_line_id (active commercial claim)
        - Cancel active qty.assignment rows
        - Refresh related MTX from live assignments (idempotent)
        Cancelled PO remains on M2M for audit but must not block approval
        once active coverage is zero (see _check_no_cancelled_documents).
        """
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        Line = margin_acl.margin_transaction_line(self.env)
        Assign = (
            self.env["justech.purchase.sale.qty.assignment"]
            if "justech.purchase.sale.qty.assignment" in self.env
            else None
        )
        svc = LineAllocationService(self.env)
        for po in self:
            lines = Line.search(
                [
                    ("purchase_order_id", "=", po.id),
                    ("line_type", "=", "cost"),
                    ("state", "!=", "excluded"),
                ]
            )
            if lines:
                lines.with_context(skip_line_sync=True).write({"state": "excluded"})
            pols = po.order_line.filtered(lambda l: not l.display_type)
            if Assign:
                asgs = Assign.search(
                    [
                        ("purchase_line_id", "in", pols.ids),
                        ("state", "=", "active"),
                    ]
                )
                if asgs:
                    asgs.write({"state": "cancelled"})
            for pol in pols.filtered("sale_line_id"):
                pol.with_context(skip_line_sync=True).write({"sale_line_id": False})
            txs = self.env["purchase.sale.margin.transaction"].search(
                [("purchase_order_ids", "in", po.id)]
            )
            for tx in txs:
                svc.refresh_estimated_costs_from_live_assignments(tx)

    def action_create_invoice(self, attachment_ids=False):
        """Block silent RD$0 vendor bills when nothing is receivable/billable yet.

        Standard Odoo can create posted bills with qty 0 (receive policy, no receipt)
        which then appear as «Pagado». Prefer a human message over that trap.
        """
        for order in self:
            product_lines = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            )
            if not product_lines:
                continue
            to_invoice = sum(product_lines.mapped("qty_to_invoice") or [0.0])
            if float_is_zero(to_invoice, precision_digits=4):
                raise UserError(
                    _(
                        "No hay cantidades disponibles para facturar.\n"
                        "Primero registre la recepción de los productos."
                    )
                )
        return super().action_create_invoice(attachment_ids=attachment_ids)

    def button_cancel(self):
        res = super().button_cancel()
        self._margin_exclude_cost_lines_on_cancel()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "cancel":
            self._margin_exclude_cost_lines_on_cancel()
        return res
